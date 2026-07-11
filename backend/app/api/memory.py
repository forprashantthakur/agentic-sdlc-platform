from __future__ import annotations

from fastapi import APIRouter, Query

from app.memory import rag

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
