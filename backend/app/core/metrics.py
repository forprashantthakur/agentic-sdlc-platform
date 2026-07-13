"""Telemetry. Per-agent, per-model, per-call — latency, tokens, cost, retries, failures.

Deliberately in-process and lock-guarded rather than Prometheus/OTel: this platform has one backend
and a handful of calls per run, and a metrics stack you have to operate is a cost you pay every day
to answer a question you ask twice a week. The `/api/metrics` payload is shaped so a Prometheus
exporter or an OTel bridge is a fifty-line adapter when you actually need one — the measurement is
the hard part, and it is done here.

Percentiles are computed over a bounded ring buffer, so memory is O(1) and a long-running process
does not slowly eat the box.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

RING = 500          # per-key samples retained for percentiles

# Rupees per million tokens, in / out. Rough, and deliberately visible: an agentic platform whose
# cost you cannot state is one nobody will approve.
PRICING: dict[str, tuple[float, float]] = {
    "gemini-3.1-pro":        (170.0, 1020.0),
    "gemini-3.1-pro-preview": (170.0, 1020.0),
    "gemini-3.5-flash":      (25.0, 210.0),
    "gemini-3.1-flash":      (25.0, 210.0),
    "gemini-3.1-flash-lite": (8.0, 34.0),
    "claude-opus-4-8":       (1250.0, 6250.0),
    "claude-sonnet-5":       (250.0, 1250.0),
}


def _price(model: str, tin: int, tout: int) -> float:
    for key, (pin, pout) in PRICING.items():
        if key in (model or ""):
            return (tin / 1e6) * pin + (tout / 1e6) * pout
    return 0.0


@dataclass
class Series:
    count: int = 0
    errors: int = 0
    retries: int = 0
    cache_hits: int = 0
    total_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=RING))

    def snapshot(self) -> dict[str, Any]:
        s = sorted(self.samples)
        def pct(p: float) -> float:
            if not s:
                return 0.0
            return round(s[min(int(len(s) * p), len(s) - 1)], 1)
        return {
            "calls": self.count,
            "errors": self.errors,
            "retries": self.retries,
            "cache_hits": self.cache_hits,
            "mean_ms": round(self.total_ms / self.count, 1) if self.count else 0.0,
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "max_ms": round(max(s), 1) if s else 0.0,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_inr": round(self.cost_inr, 2),
        }


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_agent: dict[str, Series] = defaultdict(Series)
        self._by_model: dict[str, Series] = defaultdict(Series)
        self._by_stage: dict[str, Series] = defaultdict(Series)   # rag, llm, provider, pipeline
        self._concurrency = 0
        self._peak_concurrency = 0
        self._started = time.time()

    # ── recording ─────────────────────────────────────────────────────────────
    def record(self, *, agent: str | None, model: str | None, stage: str, ms: float,
               tokens_in: int = 0, tokens_out: int = 0, error: bool = False,
               retries: int = 0, cache_hit: bool = False) -> None:
        cost = _price(model or "", tokens_in, tokens_out)
        with self._lock:
            for key, table in ((agent, self._by_agent), (model, self._by_model), (stage, self._by_stage)):
                if not key:
                    continue
                s = table[key]
                s.count += 1
                s.total_ms += ms
                s.samples.append(ms)
                s.tokens_in += tokens_in
                s.tokens_out += tokens_out
                s.cost_inr += cost
                s.errors += int(error)
                s.retries += retries
                s.cache_hits += int(cache_hit)

    @contextmanager
    def timed(self, *, agent: str | None = None, model: str | None = None, stage: str = "llm"):
        """Times a block and records it, whatever happens inside — including the failure path,
        because a metric that only counts successes is how you end up with a 100% success rate and
        an angry user."""
        t0 = time.perf_counter()
        with self._lock:
            self._concurrency += 1
            self._peak_concurrency = max(self._peak_concurrency, self._concurrency)
        box: dict[str, Any] = {"tokens_in": 0, "tokens_out": 0, "retries": 0, "cache_hit": False,
                               "model": model}
        try:
            yield box
        except Exception:
            self.record(agent=agent, model=box.get("model") or model, stage=stage,
                        ms=(time.perf_counter() - t0) * 1000, error=True,
                        retries=box.get("retries", 0))
            raise
        else:
            self.record(agent=agent, model=box.get("model") or model, stage=stage,
                        ms=(time.perf_counter() - t0) * 1000,
                        tokens_in=box.get("tokens_in", 0), tokens_out=box.get("tokens_out", 0),
                        retries=box.get("retries", 0), cache_hit=box.get("cache_hit", False))
        finally:
            with self._lock:
                self._concurrency -= 1

    # ── reporting ─────────────────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            agents = {k: v.snapshot() for k, v in self._by_agent.items()}
            models = {k: v.snapshot() for k, v in self._by_model.items()}
            stages = {k: v.snapshot() for k, v in self._by_stage.items()}
            peak, uptime = self._peak_concurrency, time.time() - self._started

        total_cost = sum(m["cost_inr"] for m in models.values())
        total_calls = sum(m["calls"] for m in models.values())
        total_retries = sum(m["retries"] for m in models.values())
        return {
            "uptime_s": round(uptime),
            "peak_concurrency": peak,
            "totals": {
                "llm_calls": total_calls,
                "retries": total_retries,
                "retry_rate": round(total_retries / total_calls, 3) if total_calls else 0.0,
                "tokens_in": sum(m["tokens_in"] for m in models.values()),
                "tokens_out": sum(m["tokens_out"] for m in models.values()),
                "cost_inr": round(total_cost, 2),
                "cache_hits": sum(m["cache_hits"] for m in models.values()),
            },
            "by_agent": agents,
            "by_model": models,
            "by_stage": stages,
        }

    def reset(self) -> None:
        with self._lock:
            self._by_agent.clear(); self._by_model.clear(); self._by_stage.clear()
            self._peak_concurrency = 0
            self._started = time.time()


metrics = Metrics()
