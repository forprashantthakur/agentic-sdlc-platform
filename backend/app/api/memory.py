from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.memory import rag
from app.memory.vector_store import get_vector_store
from app.models import Project, Source

router = APIRouter(prefix="/api/memory", tags=["memory"])

NAMESPACES = ["source", "requirement", "artifact", "reviewer_feedback", "org_standard"]


@router.get("/search")
def search(
    project_id: str,
    q: str,
    k: int = 8,
    namespaces: list[str] = Query(default=[]),
):
    """Inspect what the agents will actually retrieve. Indispensable when a generation looks wrong —
    9 times out of 10 the answer is that the wrong chunks were retrieved, not that the model is dumb."""
    hits = rag.retrieve(
        project_id=project_id, query=q, k=k, namespaces=namespaces or None
    )
    return {"query": q, "namespaces": namespaces or NAMESPACES, "hits": hits}


@router.post("/org-standard")
def add_org_standard(project_id: str, title: str, content: str):
    """Load a bank-wide standard (RBI circular, API convention, NFR baseline) into long-term memory."""
    n = rag.index(
        project_id=project_id, content=f"{title}\n\n{content}",
        namespace="org_standard", meta={"title": title},
    )
    return {"indexed_chunks": n}


@router.post("/reindex")
def reindex(project_id: str, db: Session = Depends(get_session)):
    """Purge and rebuild a project's vector memory.

    You need this the moment you switch between mock and live embeddings — and it is not obvious
    that you do, which is exactly why it is here.

    Mock mode embeds with a deterministic hash. Gemini embeds semantically. The two live in the
    same table and are mathematically meaningless against each other: a project seeded in mock mode
    and then queried live will retrieve near-random chunks, and the agents will ground their
    requirements in whatever noise came back. That failure is silent — the citations will look
    perfectly plausible and be wrong.

    So: after turning Gemini on, re-index every project that was created before.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    get_vector_store().purge(project_id=project_id)

    chunks = 0
    sources = db.query(Source).filter(Source.project_id == project_id).all()
    for s in sources:
        if not s.content.strip():
            continue
        chunks += rag.index(
            project_id=project_id,
            content=f"[{s.kind.value}] {s.title}\n\n{s.content}",
            namespace="source", source_id=s.id,
            meta={"kind": s.kind.value, "title": s.title},
        )

    ctx = project.context or {}
    if any(v for v in ctx.values()):
        chunks += rag.index(
            project_id=project_id,
            content="\n".join(
                f"{k.replace('_', ' ').title()}: {v if not isinstance(v, list) else ', '.join(v)}"
                for k, v in ctx.items() if v
            ),
            namespace="source",
            meta={"kind": "BUSINESS_CONTEXT", "title": "Business Context (intake form)"},
        )

    from app.llm.gemini import gemini
    return {
        "project": project.name,
        "sources_reindexed": len(sources),
        "chunks": chunks,
        "embedding_model": gemini().model_name if gemini().live else "mock/deterministic",
        "note": "Artifact and reviewer-feedback namespaces are not rebuilt — re-run the agents to "
                "regenerate those.",
    }
