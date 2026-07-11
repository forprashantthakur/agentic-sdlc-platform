from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import Project, Run, Source
from app.schemas import ProjectIn, ProjectOut, SourceIn
from app.seed import SEED_SOURCES

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _out(db: Session, p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id, name=p.name, business_unit=p.business_unit, description=p.description,
        created_at=p.created_at,
        source_count=db.scalar(select(func.count()).select_from(Source).where(Source.project_id == p.id)) or 0,
        run_count=db.scalar(select(func.count()).select_from(Run).where(Run.project_id == p.id)) or 0,
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_session)):
    return [_out(db, p) for p in db.scalars(select(Project).order_by(Project.created_at.desc()))]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_session)):
    p = Project(name=body.name, business_unit=body.business_unit, description=body.description)
    db.add(p)
    db.flush()
    for s in body.sources:
        db.add(Source(project_id=p.id, kind=s.kind, title=s.title, content=s.content, meta=s.meta))
    db.flush()
    return _out(db, p)


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
