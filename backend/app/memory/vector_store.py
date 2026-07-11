"""Long-term memory backing store.

PgVectorStore is what runs in the compose stack. InMemoryVectorStore is the fallback
so the graph is testable without Postgres — same interface, same cosine ranking,
so retrieval behaviour is genuinely exercised either way.
"""

from __future__ import annotations

import json
import math
import uuid
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import text

from app.core.config import settings


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, *, project_id: str, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> int: ...

    @abstractmethod
    def search(self, *, project_id: str, embedding: list[float], k: int = 6,
               namespaces: list[str] | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def purge(self, *, project_id: str, namespace: str | None = None) -> None: ...


class PgVectorStore(VectorStore):
    DDL = """
    CREATE TABLE IF NOT EXISTS memory_chunks (
        id          TEXT PRIMARY KEY,
        project_id  TEXT NOT NULL,
        namespace   TEXT NOT NULL,
        source_id   TEXT,
        content     TEXT NOT NULL,
        meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
        embedding   VECTOR(%(dim)s) NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS memory_chunks_project_idx ON memory_chunks (project_id, namespace);
    CREATE INDEX IF NOT EXISTS memory_chunks_vec_idx
        ON memory_chunks USING hnsw (embedding vector_cosine_ops);
    """

    def __init__(self, engine) -> None:
        self.engine = engine
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            c.execute(text(self.DDL % {"dim": settings.embed_dim}))

    def upsert(self, *, project_id, chunks, embeddings) -> int:
        rows = [
            {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "namespace": c.get("namespace", "source"),
                "source_id": c.get("source_id"),
                "content": c["content"],
                "meta": json.dumps(c.get("meta", {})),
                "embedding": "[" + ",".join(f"{v:.6f}" for v in e) + "]",
            }
            for c, e in zip(chunks, embeddings, strict=True)
        ]
        if not rows:
            return 0
        with self.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO memory_chunks (id, project_id, namespace, source_id, content, meta, embedding) "
                    "VALUES (:id, :project_id, :namespace, :source_id, :content, CAST(:meta AS JSONB), CAST(:embedding AS vector))"
                ),
                rows,
            )
        return len(rows)

    def search(self, *, project_id, embedding, k=6, namespaces=None):
        vec = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"
        ns_clause = ""
        params: dict[str, Any] = {"pid": project_id, "vec": vec, "k": k}
        if namespaces:
            ns_clause = "AND namespace = ANY(:ns)"
            params["ns"] = namespaces
        sql = text(
            f"""
            SELECT content, namespace, source_id, meta,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM memory_chunks
            WHERE project_id = :pid {ns_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        )
        with self.engine.begin() as c:
            return [dict(r._mapping) for r in c.execute(sql, params)]

    def purge(self, *, project_id, namespace=None):
        sql = "DELETE FROM memory_chunks WHERE project_id = :pid"
        params = {"pid": project_id}
        if namespace:
            sql += " AND namespace = :ns"
            params["ns"] = namespace
        with self.engine.begin() as c:
            c.execute(text(sql), params)


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    def upsert(self, *, project_id, chunks, embeddings) -> int:
        for c, e in zip(chunks, embeddings, strict=True):
            self._rows.append(
                {
                    "project_id": project_id,
                    "namespace": c.get("namespace", "source"),
                    "source_id": c.get("source_id"),
                    "content": c["content"],
                    "meta": c.get("meta", {}),
                    "embedding": e,
                }
            )
        return len(chunks)

    def search(self, *, project_id, embedding, k=6, namespaces=None):
        def cos(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            na = math.sqrt(sum(x * x for x in a)) or 1.0
            nb = math.sqrt(sum(y * y for y in b)) or 1.0
            return dot / (na * nb)

        cands = [
            r for r in self._rows
            if r["project_id"] == project_id and (not namespaces or r["namespace"] in namespaces)
        ]
        scored = [{**{k2: v for k2, v in r.items() if k2 != "embedding"},
                   "score": cos(embedding, r["embedding"])} for r in cands]
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    def purge(self, *, project_id, namespace=None):
        self._rows = [
            r for r in self._rows
            if not (r["project_id"] == project_id and (namespace is None or r["namespace"] == namespace))
        ]


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        from app.core.db import IS_POSTGRES, engine

        _store = PgVectorStore(engine) if IS_POSTGRES else InMemoryVectorStore()
    return _store
