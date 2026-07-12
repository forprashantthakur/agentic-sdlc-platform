from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters import registry
from app.core.db import get_session
from app.models import (
    Approval, ApprovalStatus, Artifact, ArtifactType, ArtifactVersion, Project, Run, RunStatus, Source,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

AGENTS = [
    ("agent1_requirements", "Requirement Gathering", "Meeting notes, emails, transcripts → structured requirements"),
    ("agent2_concept_note", "Concept Note", "Objectives, scope, business rules, risks"),
    ("agent3_wireframe", "Wireframe", "Screen spec → Figma via MCP"),
    ("agent4_requirement_docs", "Requirement Documents", "BRD · FRD · SRS · Stories · APIs · NFRs"),
    ("agent5_approval", "Approval", "Approval emails, comments, versioning, gates"),
    ("agent6_sprint", "Sprint", "Epics, stories, points → Jira"),
]


@router.get("/stats")
def stats(db: Session = Depends(get_session)):
    def n(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    # "AI accuracy" is a claim, so it must be computed from something real: the mean extraction
    # confidence across every requirement the agents actually emitted — not a number invented to
    # make a dashboard look good.
    confidences: list[float] = []
    reqs = 0
    for v in db.scalars(
        select(ArtifactVersion).join(Artifact).where(Artifact.type == ArtifactType.BUSINESS_REQUIREMENTS)
    ):
        for r in (v.payload or {}).get("requirements", []):
            reqs += 1
            if isinstance(r.get("confidence"), (int, float)):
                confidences.append(float(r["confidence"]))

    week = datetime.now(timezone.utc) - timedelta(days=7)

    return {
        "projects": n(Project),
        "requirements_extracted": reqs,
        "documents_processed": n(Source),
        "artifacts_generated": n(ArtifactVersion),
        "pending_reviews": n(Approval, Approval.status == ApprovalStatus.PENDING),
        "runs_total": n(Run),
        "runs_completed": n(Run, Run.status == RunStatus.COMPLETED),
        "runs_active": n(Run, Run.status.in_([RunStatus.RUNNING, RunStatus.PENDING])),
        "runs_waiting": n(Run, Run.status == RunStatus.WAITING_APPROVAL),
        "runs_failed": n(Run, Run.status == RunStatus.FAILED),
        "runs_this_week": n(Run, Run.started_at >= week),
        "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "integrations": registry.describe(),
        "agents": [{"id": a, "name": n_, "description": d, "status": "READY"} for a, n_, d in AGENTS],
    }


@router.get("/queue")
def queue(db: Session = Depends(get_session)):
    """Processing queue — what the agents are chewing on right now."""
    rows = db.scalars(
        select(Run)
        .where(Run.status.in_([RunStatus.RUNNING, RunStatus.PENDING, RunStatus.WAITING_APPROVAL]))
        .order_by(Run.started_at.desc()).limit(10)
    ).all()
    out = []
    for r in rows:
        project = db.get(Project, r.project_id)
        out.append({
            "run_id": r.id, "project_id": r.project_id,
            "project": project.name if project else "—",
            "status": r.status.value, "node": r.current_node, "started_at": r.started_at,
        })
    return out
