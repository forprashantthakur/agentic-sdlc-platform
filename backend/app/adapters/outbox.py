"""A shared outbound-mail record.

Every adapter — mock, Gmail, SMTP — records what it sent here. That is what lets the UI render an
"Approval Outbox": when a run hits a gate and triggers an email, the demo can show the exact message
that went to the approver, rendered as they would see it, with its one-click buttons live.

It is deliberately in-process and capped: this is a demo/observability aid, not durable mail storage.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()
_MAX = 100
_OUTBOX: deque[dict[str, Any]] = deque(maxlen=_MAX)


def record(*, to, subject, html, thread_id=None, message_id=None,
           delivery="mock", error: str | None = None) -> dict[str, Any]:
    """Record one outbound email. `delivery` is how it actually went: mock | smtp | gmail."""
    rec = {
        "message_id": message_id or uuid.uuid4().hex[:16],
        "thread_id": thread_id or uuid.uuid4().hex[:16],
        "to": to if isinstance(to, list) else [to],
        "subject": subject,
        "html": html,
        "delivery": delivery,          # what the recipient actually got: real send vs captured-only
        "error": error,                # set if a real send was attempted and failed
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    with _LOCK:
        _OUTBOX.appendleft(rec)
    return rec


def all() -> list[dict[str, Any]]:
    with _LOCK:
        return list(_OUTBOX)


def clear() -> int:
    with _LOCK:
        n = len(_OUTBOX)
        _OUTBOX.clear()
    return n
