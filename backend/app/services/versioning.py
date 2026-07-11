"""Artifact versioning.

Rules the platform enforces:
  * Artifacts are append-only. An agent never mutates a version — it writes a new one.
  * Content-addressed: an identical regeneration does not create a new version, so a
    retry or a replay is idempotent and doesn't pollute the audit trail.
  * `approved` is a property of a *version*, not of an artifact. Approving v3 does not
    retroactively approve v4.
  * Every version records the agent and the exact model that produced it — required
    for model-risk-management sign-off.
"""

from __future__ import annotations

import difflib
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Artifact, ArtifactType, ArtifactVersion


def content_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def get_artifact(db: Session, project_id: str, atype: ArtifactType) -> Artifact | None:
    return db.scalar(
        select(Artifact).where(Artifact.project_id == project_id, Artifact.type == atype)
    )


def latest(db: Session, project_id: str, atype: ArtifactType) -> ArtifactVersion | None:
    art = get_artifact(db, project_id, atype)
    if not art or not art.versions:
        return None
    return max(art.versions, key=lambda v: v.version)


def latest_approved(db: Session, project_id: str, atype: ArtifactType) -> ArtifactVersion | None:
    art = get_artifact(db, project_id, atype)
    if not art:
        return None
    approved = [v for v in art.versions if v.approved]
    return max(approved, key=lambda v: v.version) if approved else None


def commit_version(
    db: Session,
    *,
    project_id: str,
    atype: ArtifactType,
    payload: dict,
    rendered_md: str,
    produced_by: str,
    run_id: str | None,
    model: str,
    change_summary: str = "",
    external_ref: str | None = None,
) -> ArtifactVersion:
    art = get_artifact(db, project_id, atype)
    if art is None:
        art = Artifact(project_id=project_id, type=atype, current_version=0)
        db.add(art)
        db.flush()

    h = content_hash(payload)
    current = latest(db, project_id, atype)
    if current and current.content_hash == h:
        # Deterministic no-op regeneration: reuse the version, keep the trail clean.
        return current

    version = ArtifactVersion(
        artifact_id=art.id,
        version=art.current_version + 1,
        payload=payload,
        rendered_md=rendered_md,
        produced_by=produced_by,
        run_id=run_id,
        model=model,
        content_hash=h,
        change_summary=change_summary,
        external_ref=external_ref,
        approved=False,
    )
    art.current_version = version.version
    db.add(version)
    db.flush()
    return version


def approve(db: Session, version: ArtifactVersion) -> ArtifactVersion:
    version.approved = True
    db.add(version)
    db.flush()
    return version


def diff(a: ArtifactVersion | None, b: ArtifactVersion) -> str:
    """Unified diff of the rendered markdown — what a reviewer actually wants to see."""
    old = (a.rendered_md if a else "").splitlines(keepends=True)
    new = b.rendered_md.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old, new,
            fromfile=f"v{a.version}" if a else "v0 (new)",
            tofile=f"v{b.version}",
            lineterm="\n",
        )
    ) or "(no textual change)"
