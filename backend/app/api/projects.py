from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.memory import rag
from app.models import Artifact, Project, Run, RunStatus, Source
from app.schemas import BusinessContext, ProjectIn, ProjectOut, SourceIn
from app.seed import SEED_SOURCES
from app.services import ingest

MAX_UPLOAD_MB = 25

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _status(db: Session, p: Project) -> str:
    """What a project manager actually wants from a list: where is this thing?"""
    runs = db.scalars(select(Run).where(Run.project_id == p.id).order_by(Run.started_at.desc())).all()
    if not runs:
        return "DRAFT"
    return {
        RunStatus.COMPLETED: "COMPLETED",
        RunStatus.WAITING_APPROVAL: "AWAITING APPROVAL",
        RunStatus.RUNNING: "IN PROGRESS",
        RunStatus.PENDING: "IN PROGRESS",
        RunStatus.FAILED: "FAILED",
        RunStatus.REJECTED: "REJECTED",
    }.get(runs[0].status, "DRAFT")


def _out(db: Session, p: Project) -> ProjectOut:
    def count(model):
        return db.scalar(select(func.count()).select_from(model).where(model.project_id == p.id)) or 0

    return ProjectOut(
        id=p.id, name=p.name, business_unit=p.business_unit, description=p.description,
        context=p.context or {}, created_at=p.created_at,
        source_count=count(Source), run_count=count(Run), artifact_count=count(Artifact),
        status=_status(db, p),
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_session)):
    return [_out(db, p) for p in db.scalars(select(Project).order_by(Project.created_at.desc()))]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_session)):
    p = Project(
        name=body.name, business_unit=body.business_unit, description=body.description,
        context=body.context.model_dump(),
    )
    db.add(p)
    db.flush()
    for s in body.sources:
        db.add(Source(project_id=p.id, kind=s.kind, title=s.title, content=s.content, meta=s.meta))
    db.flush()

    # The business context is itself evidence. Agent 1 should be able to cite the sponsor's
    # stated objective, not just the meeting notes — so it goes into long-term memory too.
    ctx = body.context.model_dump()
    if any(v for v in ctx.values()):
        rag.index(
            project_id=p.id,
            content="\n".join(
                f"{k.replace('_', ' ').title()}: {v if not isinstance(v, list) else ', '.join(v)}"
                for k, v in ctx.items() if v
            ),
            namespace="source",
            meta={"kind": "BUSINESS_CONTEXT", "title": "Business Context (intake form)"},
        )
    return _out(db, p)


@router.patch("/{project_id}/context", response_model=ProjectOut)
def update_context(project_id: str, body: BusinessContext, db: Session = Depends(get_session)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    p.context = body.model_dump()
    db.flush()
    return _out(db, p)


@router.post("/{project_id}/upload", status_code=201)
async def upload(
    project_id: str, files: list[UploadFile] = File(...), db: Session = Depends(get_session)
):
    """Ingest uploaded files: extract text, store as a Source, index into long-term memory.

    Reports honestly per file. A scanned PDF comes back OCR_PENDING rather than as a silent
    zero-requirement source — an agent that cannot read a document must not pretend it did.
    """
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")

    results = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            results.append({"filename": f.filename, "status": "TOO_LARGE", "chars": 0, "chunks": 0,
                            "kind": "DOCUMENT", "pages": 0,
                            "note": f"Exceeds the {MAX_UPLOAD_MB}MB limit."})
            continue

        ex = ingest.extract(f.filename or "unnamed", data)
        src = Source(
            project_id=project_id, kind=ex.kind, title=f.filename or "unnamed", content=ex.text,
            meta={"status": ex.status, "note": ex.note, "pages": ex.pages,
                  "bytes": len(data), "content_type": f.content_type or ""},
        )
        db.add(src)
        db.flush()

        chunks = 0
        if ex.text.strip():
            chunks = rag.index(
                project_id=project_id, content=f"[{ex.kind.value}] {f.filename}\n\n{ex.text}",
                namespace="source", source_id=src.id,
                meta={"kind": ex.kind.value, "title": f.filename},
            )

        results.append({
            "id": src.id, "filename": f.filename, "kind": ex.kind.value, "status": ex.status,
            "note": ex.note, "chars": len(ex.text), "pages": ex.pages, "chunks": chunks,
        })

    return {"uploaded": len(results), "files": results}


@router.delete("/{project_id}/sources/{source_id}", status_code=204)
def delete_source(project_id: str, source_id: str, db: Session = Depends(get_session)):
    src = db.get(Source, source_id)
    if not src or src.project_id != project_id:
        raise HTTPException(404, "Source not found")
    db.delete(src)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_session)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return _out(db, p)


@router.post("/{project_id}/sources", status_code=201)
def add_source(project_id: str, body: SourceIn, db: Session = Depends(get_session)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    s = Source(project_id=project_id, kind=body.kind, title=body.title,
               content=body.content, meta=body.meta)
    db.add(s)
    db.flush()
    return {"id": s.id}


@router.get("/{project_id}/sources")
def list_sources(project_id: str, db: Session = Depends(get_session)):
    rows = db.scalars(select(Source).where(Source.project_id == project_id)).all()
    return [
        {"id": s.id, "kind": s.kind.value, "title": s.title,
         "chars": len(s.content), "preview": s.content[:280], "created_at": s.created_at}
        for s in rows
    ]


@router.post("/seed", response_model=ProjectOut, status_code=201)
def seed(db: Session = Depends(get_session)):
    """One-call demo bootstrap: a real project with meeting notes, an email thread and a transcript."""
    p = Project(
        name="UPI AutoPay Self-Service",
        business_unit="Retail Banking — Digital Channels",
        description="Enable retail customers to create and manage UPI AutoPay mandates in MobileBanking.",
    )
    db.add(p)
    db.flush()
    for s in SEED_SOURCES:
        db.add(Source(project_id=p.id, kind=s["kind"], title=s["title"], content=s["content"]))
    db.flush()
    return _out(db, p)
