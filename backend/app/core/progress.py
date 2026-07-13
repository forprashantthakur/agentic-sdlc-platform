"""A channel from deep inside the LLM client back to the run timeline.

Retries happened in silence. The client would back off — 4s, 8s, 16s, 32s — and the console showed
nothing but "agent1_requirements started". Three minutes of honest waiting looked exactly like a
hang, which in a demo is worse than an error: an error you can explain.

A contextvar rather than passing a callback down five layers, because the LLM client has no business
knowing what a Run is. The graph node sets the channel; the client just speaks into it if someone is
listening.
"""

from __future__ import annotations

import contextvars
from typing import Callable

# (message, level) -> writes a RunEvent for the node currently executing
_emit: contextvars.ContextVar[Callable[[str, str], None] | None] = contextvars.ContextVar(
    "run_progress", default=None
)


def set_channel(fn: Callable[[str, str], None] | None) -> contextvars.Token:
    return _emit.set(fn)


def reset_channel(token: contextvars.Token) -> None:
    _emit.reset(token)


def emit(message: str, level: str = "info") -> None:
    """Tell the user what is happening. Never raise — progress reporting must not break a run."""
    fn = _emit.get()
    if fn is None:
        return
    try:
        fn(message, level)
    except Exception:  # noqa: BLE001 - a broken timeline must never fail an agent
        pass
