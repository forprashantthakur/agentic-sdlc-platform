from __future__ import annotations

from fastapi import APIRouter

from app.core.metrics import metrics
from app.llm import health

router = APIRouter(prefix="/api/metrics", tags=["ops"])


@router.get("")
def snapshot():
    """Dashboard-ready telemetry: latency (mean/p50/p95/p99), tokens, cost, retries, cache hits,
    concurrency — per agent, per model, per stage (rag / llm / pipeline / cache).

    Deliberately in-process rather than Prometheus: this is one backend with a handful of calls per
    run, and a metrics stack you have to operate is a daily cost paid to answer a weekly question.
    The payload is shaped so an exporter is a fifty-line adapter when you genuinely need one — the
    measurement is the hard part, and it is done.
    """
    snap = metrics.snapshot()
    snap["circuit_breakers"] = health.snapshot()
    return snap


@router.post("/reset")
def reset():
    metrics.reset()
    return {"reset": True}
