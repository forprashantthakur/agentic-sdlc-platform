"""Which Jira project does this requirement belong in?

Until now every platform project pushed into one global JIRA_PROJECT_KEY, so a Corporate FX
requirement and a UPI AutoPay requirement landed in the same backlog — which defeats the point of
traceability. Each platform project now resolves to its own Jira project, once, and remembers it.

Resolution order:
  1. a key already stored on the project (so re-runs never create a duplicate);
  2. an existing Jira project whose key matches the derived one (adopt it);
  3. create one, if JIRA_AUTO_CREATE_PROJECT is on and the account may;
  4. fall back to the configured global key — a run must never fail because provisioning did.
"""

from __future__ import annotations

import re
from typing import Any

from app.adapters import registry
from app.core.config import settings
from app.core.logging import log
from app.models import Project

_STOP = {"the", "and", "for", "of", "a", "an", "to", "in", "on", "new", "requirement"}


def derive_key(name: str) -> str:
    """A Jira key from a project name: uppercase letters/digits, 2-10 chars, starts with a letter.

    "Corporate FX Booking Portal" -> CFBP;  "UPI AutoPay Self-Service" -> UASS.
    """
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name or "") if w.lower() not in _STOP]
    key = "".join(w[0] for w in words).upper()
    if len(key) < 2:                       # too few words — fall back to the first letters
        key = re.sub(r"[^A-Za-z0-9]", "", name or "").upper()[:4]
    key = re.sub(r"^[^A-Z]+", "", key) or "SDLC"     # Jira keys must start with a letter
    return key[:10]


def _is_mock() -> bool:
    return settings.is_mocked("jira") or not (settings.jira_token and settings.jira_base_url)


def _stored(project: Project) -> str | None:
    """A remembered key — but only if it was resolved in the SAME mode we are in now.

    The mock tracker fabricates a project for any key, so a mock run would store an invented key
    like CFSSBP. Switching to live Jira then reused it and every issue failed with "the target
    project doesn't exist". Mock state must never leak into a live run, so the mode is stored
    alongside the key and a mismatch re-resolves from scratch.
    """
    jira = (project.context or {}).get("jira") or {}
    if not jira.get("project_key"):
        return None
    if bool(jira.get("mock", False)) != _is_mock():
        log.info("jira.stored_key_ignored", key=jira["project_key"],
                 stored_mock=jira.get("mock"), now_mock=_is_mock())
        return None
    return jira["project_key"]


def _store(db, project: Project, info: dict[str, Any]) -> None:
    # Reassign the whole dict so SQLAlchemy sees the JSON mutation.
    project.context = {**(project.context or {}),
                       "jira": {"project_key": info["key"], "url": info.get("url", ""),
                                "created": info.get("created", False), "mock": _is_mock()}}
    db.commit()


def resolve_project_key(db, project: Project) -> str:
    """The Jira project key for this platform project. Never raises."""
    if key := _stored(project):
        return key

    tracker = registry.tracker()
    wanted = derive_key(project.name)

    # Adopt an existing project with that key before trying to create one.
    try:
        if found := tracker.find_project(wanted):
            _store(db, project, found)
            return found["key"]
    except Exception as e:
        log.warning("jira.lookup_failed", key=wanted, error=str(e))

    if settings.jira_auto_create_project:
        # Collisions are possible (another team's key), so try a couple of suffixed variants.
        for candidate in (wanted, f"{wanted}1", f"{wanted}2"):
            try:
                info = tracker.create_project(key=candidate, name=project.name)
                _store(db, project, info)
                return info["key"]
            except Exception as e:
                log.warning("jira.create_project_failed", key=candidate, error=str(e)[:200])
        log.warning("jira.auto_create_exhausted", project=project.name)

    # Last resort: the configured global project. A run must not fail because provisioning did.
    # Verify it in live mode — handing back a key that does not exist just moves the failure.
    fallback = settings.jira_project_key
    if not _is_mock():
        try:
            if tracker.find_project(fallback):
                _store(db, project, {"key": fallback, "url": "", "created": False})
            else:
                log.error("jira.fallback_missing", key=fallback)
        except Exception as e:
            log.warning("jira.fallback_check_failed", key=fallback, error=str(e))
    return fallback
