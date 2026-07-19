"""A durable record of every outbound approval email.

Originally in-process, which was a mistake: Render restarts on every deploy and after idle, so the
Approval Outbox would come up empty while a gate sat waiting — the approver's email simply gone,
with no way to act on it. Approvals are persisted; the emails that carry them must be too.

Writes go to the database and are mirrored in a small in-memory ring so a DB hiccup never breaks
an agent mid-run — sending mail must not be able to fail a pipeline.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.core.logging import log

_LOCK = threading.Lock()
_MAX = 100
_MEM: deque[dict[str, Any]] = deque(maxlen=_MAX)


def _to_dict(row) -> dict[str, Any]:
    return {
        "message_id": row.message_id,
        "thread_id": row.thread_id,
        "to": row.to_addrs or [],
        "subject": row.subject,
        "html": row.html,
        "delivery": row.delivery,
        "error": row.error,
        "sent_at": (row.created_at or datetime.now(timezone.utc)).isoformat(),
    }


def record(*, to, subject, html, thread_id=None, message_id=None,
           delivery="mock", error: str | None = None) -> dict[str, Any]:
    """Record one outbound email. `delivery` is how it actually went: mock | smtp | gmail."""
    rec = {
        "message_id": message_id or uuid.uuid4().hex[:16],
        "thread_id": thread_id or uuid.uuid4().hex[:16],
        "to": to if isinstance(to, list) else [to],
        "subject": subject,
        "html": html,
        "delivery": delivery,
        "error": error,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    with _LOCK:
        _MEM.appendleft(rec)

    # Persist OFF the caller's thread.
    #
    # record() is invoked from inside an agent's open transaction. Writing through a second session
    # synchronously deadlocks on SQLite (whole-database write lock) and needlessly couples mail
    # storage to pipeline latency everywhere else. A daemon thread writes once the agent's
    # transaction has cleared, and a failure can never propagate into the run — an email record must
    # not be able to fail a pipeline.
    threading.Thread(target=_persist, args=(rec,), daemon=True).start()
    return rec


def _persist(rec: dict[str, Any]) -> None:
    from time import sleep

    for attempt in range(5):
        try:
            from app.core.db import SessionLocal
            from app.models import OutboundEmail

            db = SessionLocal()
            try:
                db.add(OutboundEmail(
                    message_id=rec["message_id"], thread_id=rec["thread_id"],
                    to_addrs=rec["to"], subject=rec["subject"] or "", html=rec["html"] or "",
                    delivery=rec["delivery"], error=rec["error"],
                ))
                db.commit()
                return
            finally:
                db.close()
        except Exception as e:  # locked (sqlite) or a transient DB blip — back off and retry
            if attempt == 4:
                log.warning("outbox.persist_failed", error=str(e))
            sleep(0.4 * (attempt + 1))


def all() -> list[dict[str, Any]]:
    """Newest first, from the database; falls back to the in-memory ring."""
    try:
        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models import OutboundEmail

        db = SessionLocal()
        try:
            rows = db.scalars(
                select(OutboundEmail).order_by(OutboundEmail.created_at.desc()).limit(_MAX)
            ).all()
            if rows:
                return [_to_dict(r) for r in rows]
        finally:
            db.close()
    except Exception as e:  # pragma: no cover
        log.warning("outbox.read_failed", error=str(e))
    with _LOCK:
        return list(_MEM)


def clear() -> int:
    n = 0
    try:
        from app.core.db import SessionLocal
        from app.models import OutboundEmail

        db = SessionLocal()
        try:
            n = db.query(OutboundEmail).delete()
            db.commit()
        finally:
            db.close()
    except Exception as e:  # pragma: no cover
        log.warning("outbox.clear_failed", error=str(e))
    with _LOCK:
        n = n or len(_MEM)
        _MEM.clear()
    return n
