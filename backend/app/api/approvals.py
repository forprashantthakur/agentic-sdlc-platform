from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_session
from app.models import Approval, ApprovalComment, ApprovalStatus, Run, RunStatus
from pydantic import BaseModel, Field
from app.schemas import ApprovalOut, CommentIn, DecisionIn
from app.adapters.gmail import parse_decision
from app.services import runner

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; Postgres does not. Normalise so the same code path
    works against both backends."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("", response_model=list[ApprovalOut])
def list_approvals(
    status: ApprovalStatus | None = None,
    project_id: str | None = None,
    db: Session = Depends(get_session),
):
    q = select(Approval).order_by(Approval.created_at.desc())
    if status:
        q = q.where(Approval.status == status)
    if project_id:
        q = q.where(Approval.project_id == project_id)
    return list(db.scalars(q))


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: str, db: Session = Depends(get_session)):
    a = db.get(Approval, approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    return a


@router.post("/{approval_id}/decide")
def decide(approval_id: str, body: DecisionIn, db: Session = Depends(get_session)):
    """The human-in-the-loop hinge. Records the decision, then resumes the suspended graph."""
    a = db.get(Approval, approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    if a.status != ApprovalStatus.PENDING:
        raise HTTPException(409, f"Already decided: {a.status.value}")
    if a.expires_at and _aware(a.expires_at) < datetime.now(timezone.utc):
        a.status = ApprovalStatus.EXPIRED
        db.flush()
        raise HTTPException(410, "Approval request has expired")

    a.status = body.decision
    a.decided_at = datetime.now(timezone.utc)
    for c in body.comments:
        db.add(ApprovalComment(approval_id=a.id, author=c.author, body=c.body, anchor=c.anchor))
    db.flush()

    # A gate passes only when every approver in THIS ROUND has approved. Scoping to the round
    # matters: a "changes requested" from an earlier round must not veto the current one.
    siblings = db.scalars(
        select(Approval).where(
            Approval.run_id == a.run_id, Approval.gate == a.gate, Approval.round == a.round
        )
    ).all()
    if any(s.status == ApprovalStatus.PENDING for s in siblings):
        db.commit()
        return {"status": "WAITING_FOR_OTHER_APPROVERS",
                "pending": [s.approver_email for s in siblings if s.status == ApprovalStatus.PENDING]}

    if any(s.status == ApprovalStatus.REJECTED for s in siblings):
        verdict = "REJECTED"
    elif any(s.status == ApprovalStatus.CHANGES_REQUESTED for s in siblings):
        verdict = "CHANGES_REQUESTED"
    else:
        verdict = "APPROVED"

    comments = [
        f"{c.author}{f' [{c.anchor}]' if c.anchor else ''}: {c.body}"
        for s in siblings for c in s.comments
    ]
    run = db.get(Run, a.run_id)
    run.status = RunStatus.RUNNING  # gate is closed; the graph is moving again
    db.commit()

    runner.resume_run(run=run, decision=verdict, comments=comments)
    return {"status": "RESUMED", "gate": a.gate, "verdict": verdict, "comments": len(comments)}


@router.post("/by-token/{token}/decide")
def decide_by_token(token: str, body: DecisionIn, db: Session = Depends(get_session)):
    """One-click approval straight from the email button. The token is signed and expiring."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(401, f"Invalid or expired approval token: {e}") from e

    a = db.scalar(
        select(Approval).where(
            Approval.token == token, Approval.approver_email == claims["sub"]
        )
    )
    if not a:
        raise HTTPException(404, "Approval not found for this token")
    return decide(a.id, body, db)


class ReplyIn(BaseModel):
    from_addr: str = Field(..., alias="from")
    body: str
    model_config = {"populate_by_name": True}


@router.post("/reply")
def approval_reply(payload: ReplyIn, db: Session = Depends(get_session)):
    """Inbound webhook for an approver's EMAIL REPLY.

    The other half of "decide from your inbox": some approvers click a button, some just reply
    "APPROVED, looks good". A mail provider POSTs the reply here; we parse the verdict and record it
    against that approver's oldest pending gate. parse_decision already exists and is reused verbatim
    — the reply path and the button path converge on the same decide() so there is one source of
    truth for what a decision does.
    """
    verdict = parse_decision(payload.body)
    if verdict is None:
        raise HTTPException(422, "Could not read a decision (APPROVED / REJECTED / CHANGES REQUESTED) "
                                 "from the reply.")
    email = payload.from_addr.strip().lower()
    a = db.scalar(
        select(Approval).where(
            func.lower(Approval.approver_email) == email,
            Approval.status == ApprovalStatus.PENDING,
        ).order_by(Approval.created_at.asc())
    )
    if not a:
        raise HTTPException(404, f"No pending approval found for {payload.from_addr}.")

    # The reply body becomes the approver's comment — their words, on the record.
    comments = [CommentIn(author=payload.from_addr, body=payload.body.strip()[:2000])] \
        if verdict != "APPROVED" else []
    return decide(a.id, DecisionIn(decision=ApprovalStatus(verdict), comments=comments), db)
