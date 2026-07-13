"""Circuit breaker and model health.

The retry loop we had was the worst of both worlds: it hammered a single overloaded model with
exponential backoff — 4s, 8s, 16s, 32s — while a perfectly healthy alternative sat idle. Ninety
seconds of waiting to eventually fail, when a different model would have answered in four.

The rule this encodes: **never wait if another model is available.** Backoff is what you do when you
have no alternative; it is not a virtue in itself.

A breaker OPENs after N consecutive failures, stays open for a cooldown, then admits a single probe
(HALF_OPEN). One success closes it. The cooldown is jittered — synchronised retries across workers
are how a recovering service gets knocked over a second time.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import log


class State(str, Enum):
    CLOSED = "closed"        # healthy
    OPEN = "open"            # failing; do not call
    HALF_OPEN = "half_open"  # probing


@dataclass
class Breaker:
    name: str
    threshold: int = 3            # consecutive failures before opening
    cooldown: float = 30.0        # base seconds; jittered
    max_cooldown: float = 300.0

    state: State = State.CLOSED
    failures: int = 0
    opened_at: float = 0.0
    consecutive_opens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def available(self) -> bool:
        with self._lock:
            if self.state is State.CLOSED:
                return True
            if self.state is State.OPEN:
                if time.time() - self.opened_at >= self._cooldown():
                    self.state = State.HALF_OPEN
                    log.info("breaker.half_open", model=self.name)
                    return True
                return False
            return True   # HALF_OPEN — allow the probe

    def _cooldown(self) -> float:
        # Exponential in the number of times we have re-opened, with jitter. Without the jitter,
        # every worker probes at the same instant and re-floors a service that was just recovering.
        base = min(self.cooldown * (2 ** max(self.consecutive_opens - 1, 0)), self.max_cooldown)
        return base * random.uniform(0.8, 1.3)

    def success(self) -> None:
        with self._lock:
            if self.state is not State.CLOSED:
                log.info("breaker.closed", model=self.name)
            self.state = State.CLOSED
            self.failures = 0
            self.consecutive_opens = 0

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.state is State.HALF_OPEN or self.failures >= self.threshold:
                if self.state is not State.OPEN:
                    self.consecutive_opens += 1
                    log.warning("breaker.open", model=self.name, failures=self.failures,
                                cooldown=f"{self._cooldown():.0f}s")
                self.state = State.OPEN
                self.opened_at = time.time()

    def snapshot(self) -> dict:
        return {"state": self.state.value, "failures": self.failures,
                "cooldown_remaining_s": max(0, round(self._cooldown() - (time.time() - self.opened_at)))
                if self.state is State.OPEN else 0}


_breakers: dict[str, Breaker] = {}
_lock = threading.Lock()


def breaker(model: str) -> Breaker:
    with _lock:
        if model not in _breakers:
            _breakers[model] = Breaker(name=model)
        return _breakers[model]


def snapshot() -> dict[str, dict]:
    with _lock:
        return {k: b.snapshot() for k, b in _breakers.items()}
