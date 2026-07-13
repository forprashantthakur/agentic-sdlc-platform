"""Retrieval layer.

Namespaces let each agent pull the right slice of long-term memory:
  source            – raw meeting notes / emails / transcripts (Agent 1 grounds here)
  requirement       – approved business requirements (Agents 2-4 ground here)
  artifact          – previously approved artifact sections (Agents 4-6 ground here)
  reviewer_feedback – comments from rejected approval rounds (every regeneration reads these)
  org_standard      – bank-wide standards: RBI e-mandate rules, NFR baselines, API conventions
"""

from __future__ import annotations

import re
from typing import Any

from app.core.metrics import metrics
from app.llm.gemini import gemini
from app.memory import shared
from app.memory.vector_store import get_vector_store

CHUNK_CHARS = 1200
OVERLAP = 150


def chunk_text(content: str, chunk_chars: int = CHUNK_CHARS, overlap: int = OVERLAP) -> list[str]:
    """Paragraph-aware chunking — we never split mid-sentence if we can avoid it."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= chunk_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= chunk_chars:
                buf = p
            else:
                for i in range(0, len(p), chunk_chars - overlap):
                    chunks.append(p[i : i + chunk_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks or [content[:chunk_chars]]


def index(
    *, project_id: str, content: str, namespace: str,
    source_id: str | None = None, meta: dict[str, Any] | None = None,
) -> int:
    pieces = chunk_text(content)
    chunks = [
        {"content": p, "namespace": namespace, "source_id": source_id, "meta": meta or {}}
        for p in pieces
    ]
    embeddings = gemini().embed([c["content"] for c in chunks])
    return get_vector_store().upsert(project_id=project_id, chunks=chunks, embeddings=embeddings)


def retrieve(
    *, project_id: str, query: str, k: int = 6, namespaces: list[str] | None = None,
    min_score: float | None = None,
) -> list[dict[str, Any]]:
    """`min_score` is opt-in: cosine similarity is legitimately negative, and a naive
    `>= 0` floor silently drops valid hits. Callers that want a relevance floor set one."""
    # One retrieval per (query, k, namespaces) per run. Agent 2 and Agent 4 both ask for
    # "regulatory constraints for this capability" over evidence that cannot have changed between
    # them — that is an embedding call and a vector search spent proving what we already knew.
    memo = shared.cached(project_id, query, k, namespaces)
    if memo is not None:
        hits = memo
    else:
        with metrics.timed(stage="rag"):
            emb = gemini().embed([query])[0]
            hits = get_vector_store().search(
                project_id=project_id, embedding=emb, k=k, namespaces=namespaces
            )
        shared.remember(project_id, query, k, namespaces, hits)

    if min_score is None:
        return hits
    return [h for h in hits if h["score"] >= min_score]


def as_context(hits: list[dict[str, Any]], header: str = "RETRIEVED CONTEXT") -> str:
    if not hits:
        return ""
    body = "\n\n".join(
        f"[{i + 1}] (ns={h['namespace']}, score={h['score']:.3f})\n{h['content']}"
        for i, h in enumerate(hits)
    )
    return f"--- {header} ---\n{body}\n--- END {header} ---"
