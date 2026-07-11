from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_session
from app.models import Approval, ApprovalComment, ApprovalStatus, Run, RunStatus
from app.schemas import ApprovalOut, DecisionIn
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
