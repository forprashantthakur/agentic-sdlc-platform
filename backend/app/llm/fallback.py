"""Fallback routing: never wait if another model is available.

THE BUG THIS REPLACES

    Gemini 503 -> sleep 4s -> Gemini 503 -> sleep 8s -> Gemini 503 -> sleep 16s -> ...

Ninety seconds of blocking, on one overloaded model, while a healthy alternative sat idle. Backoff is
what you do when you have *no alternative*. It is not a virtue.

THE POLICY NOW

    try model A -> transient failure -> IMMEDIATELY try model B -> then C ...
    only if EVERY candidate is exhausted do we back off, and then with jitter.

A circuit breaker takes a model out of rotation after repeated failures, so a sick model is skipped
instantly rather than rediscovered on every call. Permanent errors (retired model, no quota, bad key)
do not trip the breaker and are not retried anywhere — waiting will never fix them, and trying the
fallback would just fail differently.

Ordering is by capability, not price: the first candidate is the model the caller asked for. The
fallbacks exist to keep a run alive, not to quietly downgrade its reasoning without saying so — which
is why every artifact version records the model that ACTUALLY produced it, not the one we intended.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.core.config import settings
from app.core.logging import log
from app.core.metrics import metrics
from app.core import progress
from app.llm.health import breaker


class AllModelsFailed(RuntimeError):
    """Every candidate is down or exhausted. This is the only case where we truly give up."""


@dataclass(frozen=True)
class Candidate:
    provider: str      # "gemini" | "anthropic"
    model: str


def chain(primary: Candidate) -> list[Candidate]:
    """The requested model first, then the configured fallbacks (skipping duplicates)."""
    out = [primary]
    for spec in settings.fallback_chain:
        spec = spec.strip()
        if not spec:
            continue
        provider, _, model = spec.partition(":")
        if not model:
            provider, model = "gemini", provider
        c = Candidate(provider.strip().lower(), model.strip())
        if c not in out:
            out.append(c)
    return out


def execute(
    *,
    primary: Candidate,
    call: Callable[[Candidate], Any],
    is_transient: Callable[[Exception], bool],
    task: str,
    agent: str | None = None,
) -> Any:
    """Run `call` against the first healthy candidate; on a transient failure move on at once."""
    candidates = chain(primary)
    tried: list[str] = []
    last: Exception | None = None
    retries = 0

    for cycle in range(settings.max_fallback_cycles):
        for c in candidates:
            key = f"{c.provider}:{c.model}"
            b = breaker(key)
            if not b.available():
                log.info("fallback.skip_unhealthy", model=key, task=task)
                continue

            try:
                with metrics.timed(agent=agent, model=c.model, stage="llm") as m:
                    result = call(c)
                    if isinstance(result, tuple) and len(result) == 2:
                        payload, usage = result
                        m["tokens_in"] = usage.get("in", 0)
                        m["tokens_out"] = usage.get("out", 0)
                        m["retries"] = retries
                        b.success()
                        return payload
                    m["retries"] = retries
                    b.success()
                    return result

            except Exception as e:                     # noqa: BLE001
                last = e
                if not is_transient(e):
                    # Permanent: a retired model, no quota, a bad key. The fallback would fail too,
                    # differently. Surface it now, with the fix named, rather than burying it under
                    # four more failures.
                    raise
                retries += 1
                tried.append(key)
                b.failure()
                log.warning("fallback.transient", model=key, task=task, error=str(e)[:120])
                progress.emit(
                    f"{key} unavailable — switching to the next model immediately (no wait).",
                    level="warning",
                )

        # Every candidate failed this cycle. NOW backing off is the right thing — with jitter,
        # because synchronised retries are how you knock over a service that was recovering.
        if cycle < settings.max_fallback_cycles - 1:
            wait = min(2 ** cycle, 20) * random.uniform(0.8, 1.3)
            log.warning("fallback.all_down", task=task, sleeping=f"{wait:.1f}s", cycle=cycle + 1)
            progress.emit(
                f"All models are overloaded. Waiting {wait:.0f}s before another attempt "
                f"(cycle {cycle + 1} of {settings.max_fallback_cycles}).",
                level="warning",
            )
            time.sleep(wait)

    raise AllModelsFailed(
        f"{task}: every candidate failed — tried {', '.join(dict.fromkeys(tried)) or 'none'}. "
        f"Last error: {last}"
    ) from last
