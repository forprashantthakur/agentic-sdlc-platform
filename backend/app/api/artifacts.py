from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import Artifact, ArtifactVersion, Project
from app.schemas import ArtifactOut, VersionDetail
from app.core.logging import log
from app.services import export, versioning

MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "md": "text/markdown",
}

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


@router.get("/versions/{version_id}/export")
def export_version(version_id: str, format: str = "docx", db: Session = Depends(get_session)):
    """Export one artifact as .docx, .pdf or .md.

    Works for every artifact type — Concept Note, BRD, FRD, SRS, Wireframes, User Stories,
    Acceptance Criteria, API Requirements, NFRs, Sprint Plan — because all of them render
    through the same block model.
    """
    if format not in MEDIA:
        raise HTTPException(400, f"Unsupported format '{format}'. Use docx, pdf or md.")

    v = db.get(ArtifactVersion, version_id)
    if not v:
        raise HTTPException(404, "Version not found")
    project = db.get(Project, v.artifact.project_id) if v.artifact else None
    if not project:
        raise HTTPException(404, "This document's project no longer exists.")

    try:
        if format == "md":
            content: bytes = v.rendered_md.encode()
        elif format == "docx":
            content = export.to_docx([v], project_name=project.name)
        else:
            content = export.to_pdf([v], project_name=project.name)
    except export.PdfEngineUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        log.exception("export.failed", version=version_id, format=format)
        raise HTTPException(500, f"Could not build the {format.upper()}: {type(e).__name__}: {str(e)[:200]}") from e

    return Response(
        content,
        media_type=MEDIA[format],
        headers={"Content-Disposition": f'attachment; filename="{export.filename(v, format)}"'},
    )


@router.get("/pack")
def export_pack(
    project_id: str,
    format: str = "pdf",
    approved_only: bool = False,
    db: Session = Depends(get_session),
):
    """Export every artifact as ONE document — the pack a sponsor or auditor actually wants.

    Ordered as a requirements pack reads: Requirements -> Concept Note -> Wireframes ->
    BRD -> FRD -> SRS -> Stories -> ACs -> APIs -> NFRs -> Sprint Plan. Each document keeps
    its own version, producing agent, model and approval status on the page — so the pack is
    self-evidencing rather than an undated blob.
    """
    if format not in ("docx", "pdf"):
        raise HTTPException(400, "Pack export supports docx or pdf.")

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    versions: list[ArtifactVersion] = []
    for atype in export.PACK_ORDER:
        v = (
            versioning.latest_approved(db, project_id, atype)
            if approved_only
            else versioning.latest(db, project_id, atype)
        )
        if v:
            versions.append(v)

    if not versions:
        raise HTTPException(
            404,
            "No artifacts to export yet."
            + (" (No approved versions — try approved_only=false.)" if approved_only else ""),
        )

    try:
        content = (
            export.to_docx(versions, project_name=project.name, pack=True)
            if format == "docx"
            else export.to_pdf(versions, project_name=project.name, pack=True)
        )
    except export.PdfEngineUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        log.exception("export.pack_failed", project=project_id, format=format)
        raise HTTPException(500, f"Could not build the {format.upper()} pack: {type(e).__name__}: {str(e)[:200]}") from e

    safe = project.name.replace(" ", "_")
    return Response(
        content,
        media_type=MEDIA[format],
        headers={"Content-Disposition": f'attachment; filename="{safe}_Requirements_Pack.{format}"'},
    )
