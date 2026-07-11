"""Short-term (working) memory = the LangGraph checkpointer + a per-run scratchpad.

Long-term memory is vector-backed and survives across runs and projects.
Short-term memory is the graph state for one run: it holds the last N agent
messages, the current draft, reviewer comments in flight, and the interrupt payload
that lets a run be suspended at an approval gate for days and then resumed exactly
where it left off.
"""

from __future__ import annotations

from contextlib import contextmanager

from app.core.config import settings
from app.core.logging import log

MAX_SCRATCH_MESSAGES = 20


def trim(messages: list[dict], limit: int = MAX_SCRATCH_MESSAGES) -> list[dict]:
    """Keep the working set bounded — the first message (the brief) plus the last N-1."""
    if len(messages) <= limit:
        return messages
    return [messages[0], *messages[-(limit - 1) :]]


@contextmanager
def checkpointer():
    """Postgres-backed checkpointer when available; MemorySaver otherwise.

    The Postgres saver is what makes an approval gate survive a backend restart —
    a run interrupted on Friday resumes on Monday from the same checkpoint.
    """
    if settings.database_url.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            dsn = settings.database_url.replace("postgresql+psycopg", "postgresql")
            with PostgresSaver.from_conn_string(dsn) as cp:
                cp.setup()
                yield cp
                return
        except Exception as e:  # pragma: no cover - infra dependent
            log.warning("checkpointer.postgres_unavailable", error=str(e))

    log.warning("checkpointer.memory", note="runs will not survive a restart")
    yield _memory_saver()


_MEM = None


def _memory_saver():
    """A single process-wide MemorySaver.

    Handing out a fresh MemorySaver per call would be a subtle disaster: the resume after an
    approval gate would attach to an empty checkpointer and the run would restart from scratch
    instead of continuing. The Postgres saver is stateless-per-connection and has no such issue.
    """
    global _MEM
    if _MEM is None:
        from langgraph.checkpoint.memory import MemorySaver

        _MEM = MemorySaver()
    return _MEM
