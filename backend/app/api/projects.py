from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.discovery_samples import sample_for
from app.core.logging import log
from app.memory import rag
from app.memory.vector_store import get_vector_store
from app.models import (
    Approval, ApprovalStatus, Artifact, ArtifactVersion, Project, Run, RunStatus, Source,
)
from app.schemas import BusinessContext, ProjectIn, ProjectOut, SourceIn
from app.seed import CATALOG, catalog_summary
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
    # A DRAFT sits in the intake queue, not the project list — showing it here would let a run be
    # started around the review step the intake queue exists to enforce.
    return [
        _out(db, p)
        for p in db.scalars(select(Project).order_by(Project.created_at.desc()))
        if (p.context or {}).get("intake", {}).get("status") != "DRAFT"
    ]


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


@router.get("/{project_id}/impact")
def delete_impact(project_id: str, db: Session = Depends(get_session)):
    """What a delete would destroy. The UI shows this BEFORE asking for confirmation.

    A project is not just rows. It is the audit trail: which human approved which version of which
    document, produced by which agent, on which model. In a governed process that record is the
    point. So we tell you exactly what you are about to lose, and we make you name the project to
    prove you meant it.
    """
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    def n(model):
        return db.scalar(select(func.count()).select_from(model).where(model.project_id == p.id)) or 0

    approved = db.scalar(
        select(func.count()).select_from(ArtifactVersion).join(Artifact)
        .where(Artifact.project_id == p.id, ArtifactVersion.approved.is_(True))
    ) or 0
    decisions = db.scalar(
        select(func.count()).select_from(Approval)
        .where(Approval.project_id == p.id, Approval.status != ApprovalStatus.PENDING)
    ) or 0

    return {
        "project": p.name,
        "sources": n(Source),
        "runs": n(Run),
        "artifacts": n(Artifact),
        "artifact_versions": db.scalar(
            select(func.count()).select_from(ArtifactVersion).join(Artifact)
            .where(Artifact.project_id == p.id)) or 0,
        "approved_versions": approved,
        "recorded_decisions": decisions,
        "irreversible": True,
        "warning": (
            "This destroys the audit trail: every approval decision, every version, and the record of "
            "which agent and which model produced each document."
            if (approved or decisions) else
            "Nothing has been approved on this project, so no sign-off record will be lost."
        ),
    }


@router.delete("/{project_id}", status_code=200)
def delete_project(project_id: str, confirm: str = "", db: Session = Depends(get_session)):
    """Delete a project and everything it owns.

    `confirm` must equal the project's name. Not a checkbox — a deliberate act of typing. Deleting
    the wrong project in a governance tool is not a recoverable mistake, and a one-click delete next
    to a project card is a trap.
    """
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")

    if confirm.strip() != p.name:
        raise HTTPException(
            400,
            f"To delete this project, pass confirm=\"{p.name}\" — its exact name. "
            "This is irreversible and destroys the approval history.",
        )

    # ORM cascades cover sources, runs, run events, artifacts and versions — they hang off
    # relationships on Project. Three things do NOT, and each is a real leak:
    #
    #   1. Approvals. Project has no ORM relationship to them, and the DB-level ON DELETE CASCADE
    #      is not enforced on SQLite. Orphaned approval rows in a governance tool are decision
    #      records pointing at a project that no longer exists.
    #   2. The vector store — long-term memory lives outside the relational schema. Leave it and a
    #      deleted project keeps answering the copilot from beyond the grave.
    #   3. LangGraph checkpoints — one thread per run. Leave them and the runs stay *resumable*: a
    #      stale approval link could wake an agent for a project that is gone.
    approvals = db.scalars(select(Approval).where(Approval.project_id == project_id)).all()
    for a in approvals:
        db.delete(a)          # ApprovalComment cascades off Approval, which does have a relationship
    db.flush()

    purged_chunks = _purge_memory(project_id)
    purged_threads = _purge_checkpoints(db, project_id)

    name = p.name
    db.delete(p)
    db.flush()
    log.warning("project.deleted", project=name, id=project_id,
                chunks=purged_chunks, threads=purged_threads)
    return {
        "deleted": name,
        "approvals_purged": len(approvals),
        "memory_purged": bool(purged_chunks),
        "checkpoint_threads_purged": purged_threads,
    }


def _purge_memory(project_id: str) -> int:
    try:
        get_vector_store().purge(project_id=project_id)
        return 1
    except Exception as e:
        log.error("project.delete.memory_purge_failed", project_id=project_id, error=str(e))
        return 0


def _purge_checkpoints(db: Session, project_id: str) -> int:
    """Drop the LangGraph checkpoints for this project's runs.

    A stranded checkpoint is not harmless: the thread stays resumable, so a stale approval link
    could wake an agent for a project that no longer exists.
    """
    from app.core.db import IS_POSTGRES, engine

    threads = [r.thread_id for r in db.scalars(select(Run).where(Run.project_id == project_id))]
    if not threads or not IS_POSTGRES:
        return 0

    from sqlalchemy import text

    n = 0
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        try:
            with engine.begin() as c:
                res = c.execute(text(f"DELETE FROM {table} WHERE thread_id = ANY(:t)"), {"t": threads})
                n += res.rowcount or 0
        except Exception as e:      # the tables may not exist yet on a fresh database
            log.info("project.delete.checkpoint_skip", table=table, error=str(e)[:80])
    return len(threads) if n else 0


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


@router.get("/demo/catalog")
def demo_catalog():
    """The demo library: five banking IT projects, each with a deliberately flawed evidence base.

    Every one carries a real conflict (two sources that disagree on a material decision) and a real
    gap (something a bank obviously needs that nobody thought to say). A seed corpus where every
    source agrees would make the agents look brilliant and prove nothing.
    """
    return catalog_summary()


def _seed_one(db: Session, key: str) -> Project:
    spec = CATALOG[key]
    p = Project(
        name=spec["name"], business_unit=spec["business_unit"],
        description=spec["description"], context=spec["context"],
    )
    db.add(p)
    db.flush()
    for kind, title, content in spec["sources"]:
        db.add(Source(project_id=p.id, kind=kind, title=title, content=content))
    db.flush()

    # Index the intake context as evidence, exactly as a real project would.
    ctx = spec["context"]
    rag.index(
        project_id=p.id,
        content="\n".join(
            f"{k.replace('_', ' ').title()}: {v if not isinstance(v, list) else ', '.join(v)}"
            for k, v in ctx.items() if v
        ),
        namespace="source",
        meta={"kind": "BUSINESS_CONTEXT", "title": "Business Context (intake form)"},
    )
    return p


@router.post("/seed", response_model=ProjectOut, status_code=201)
def seed(key: str = "upi_autopay", db: Session = Depends(get_session)):
    """Seed one demo project. Defaults to UPI AutoPay for backwards compatibility."""
    if key not in CATALOG:
        raise HTTPException(404, f"Unknown demo project '{key}'. Options: {', '.join(CATALOG)}")
    return _out(db, _seed_one(db, key))


@router.post("/seed/all", response_model=list[ProjectOut], status_code=201)
def seed_all(db: Session = Depends(get_session)):
    """Seed the whole catalogue — five projects across five business units."""
    return [_out(db, _seed_one(db, key)) for key in CATALOG]


@router.get("/{project_id}/discovery/sample")
def discovery_sample(project_id: str, db: Session = Depends(get_session)):
    """Pre-written interview answers for a seeded demo project.

    Typing ten answers live in front of a CEO is a typing test, not a demo. These are consistent with
    the project's seeded documents — same baselines, same regulator, same thresholds — because an
    interview answer that contradicted the workshop minutes would surface downstream as a conflict
    Agent 1 flags. Impressive if you meant it; embarrassing if you did not.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    answers = sample_for(project.name)
    if not answers:
        raise HTTPException(
            404,
            f"No sample interview for '{project.name}'. Sample answers exist only for the seeded "
            f"demo projects — a real project's interview is the user's to give.",
        )
    return {"project": project.name, "answers": answers}


@router.get("/cleanup/preview")
def cleanup_preview(db: Session = Depends(get_session)):
    """What a cleanup WOULD delete. Never deletes anything.

    Scoped deliberately to projects that produced no artifacts: an empty project is a false start,
    while one with a document pack is somebody's work. Bulk-deleting the latter on a single click
    is not a feature, it is an incident.
    """
    from app.models import Artifact

    rows = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    empty = []
    for p in rows:
        n = db.scalar(select(func.count()).select_from(Artifact).where(Artifact.project_id == p.id)) or 0
        if n == 0:
            empty.append({"id": p.id, "name": p.name, "created_at": p.created_at.isoformat()})
    return {"total_projects": len(rows), "deletable": len(empty),
            "kept": len(rows) - len(empty), "projects": empty[:200]}


@router.post("/cleanup")
def cleanup(confirm: str = "", db: Session = Depends(get_session)):
    """Delete every project that produced no artifacts. Requires ?confirm=DELETE-EMPTY."""
    from app.models import Artifact

    if confirm != "DELETE-EMPTY":
        raise HTTPException(400, "Pass ?confirm=DELETE-EMPTY to proceed.")

    rows = db.scalars(select(Project)).all()
    deleted = 0
    for p in rows:
        n = db.scalar(select(func.count()).select_from(Artifact).where(Artifact.project_id == p.id)) or 0
        if n == 0:
            db.delete(p)          # cascades to sources, runs and events
            deleted += 1
    db.commit()
    return {"deleted": deleted}
