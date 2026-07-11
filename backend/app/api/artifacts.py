from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import Artifact, ArtifactVersion
from app.schemas import ArtifactOut, VersionDetail
from app.services import versioning

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("", response_model=list[ArtifactOut])
def list_artifacts(project_id: str, db: Session = Depends(get_session)):
    return list(db.scalars(select(Artifact).where(Artifact.project_id == project_id)))


@router.get("/versions/{version_id}", response_model=VersionDetail)
def get_version(version_id: str, db: Session = Depends(get_session)):
    v = db.get(ArtifactVersion, version_id)
    if not v:
        raise HTTPException(404, "Version not found")
    return v


@router.get("/versions/{version_id}/markdown")
def download_markdown(version_id: str, db: Session = Depends(get_session)):
    v = db.get(ArtifactVersion, version_id)
    if not v:
        raise HTTPException(404, "Version not found")
    filename = f"{v.artifact.type.value}_v{v.version}.md"
    return Response(
        v.rendered_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/versions/{version_id}/diff")
def version_diff(version_id: str, db: Session = Depends(get_session)):
    """Diff against the immediately preceding version — what changed after the review round."""
    v = db.get(ArtifactVersion, version_id)
    if not v:
        raise HTTPException(404, "Version not found")
    prev = next((x for x in sorted(v.artifact.versions, key=lambda x: -x.version)
                 if x.version < v.version), None)
    return {
        "artifact_type": v.artifact.type.value,
        "from_version": prev.version if prev else 0,
        "to_version": v.version,
        "diff": versioning.diff(prev, v),
    }
