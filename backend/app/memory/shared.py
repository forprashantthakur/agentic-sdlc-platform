"""Per-run retrieval memoisation.

Every agent used to hit the vector store independently, and several of them asked near-identical
questions — Agent 2 and Agent 4 both retrieve "regulatory constraints for this capability", one
after the other, over evidence that cannot have changed in between. Each one is an embedding call
plus a vector search: a hundred milliseconds and a token charge, spent proving what we already knew.

Scoped to a RUN, not to a process. That boundary matters: the evidence base is immutable within a
run (sources are ingested before Agent 1 starts), so caching inside it is sound. Across runs it is
NOT sound — a re-run may follow new uploads or a reviewer's feedback, and serving a stale retrieval
there would ground an agent in evidence the user has already replaced.
"""

from __future__ import annotations

import contextvars
import threading
import hashlib
from typing import Any

from app.core.logging import log
from app.core.metrics import metrics

_cache: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "rag_cache", default=None
)


def begin_run() -> contextvars.Token:
    return _cache.set({})


def end_run(token: contextvars.Token) -> None:
    _cache.reset(token)


def _key(project_id: str, query: str, k: int, namespaces: list[str] | None) -> str:
    raw = f"{project_id}|{query}|{k}|{sorted(namespaces or [])}"
    return hashlib.sha256(raw.encode()).hexdigest()


def cached(project_id: str, query: str, k: int, namespaces: list[str] | None):
    store = _cache.get()
    if store is None:
        return None
    hit = store.get(_key(project_id, query, k, namespaces))
    if hit is not None:
        metrics.record(agent=None, model=None, stage="rag", ms=0.0, cache_hit=True)
        log.info("rag.cache_hit", query=query[:48])
    return hit


def remember(project_id: str, query: str, k: int, namespaces: list[str] | None, hits: Any) -> None:
    store = _cache.get()
    if store is not None:
        store[_key(project_id, query, k, namespaces)] = hits
