"""Confluence — the document system of record for Process Flow 2.

Flow 1's approved pack (BRD/FRD/SRS) is published here, and that publication is the entry point for
Flow 2 (PRD §2.1, §8 step 0). Follows the platform's adapter+mock pattern: real when a token is
configured, captured-in-memory otherwise so the flow is demonstrable offline.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import log


class ConfluenceAdapter:
    def __init__(self, base_url: str, email: str, token: str, space: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = (email, token)
        self.space = space

    def publish(self, *, title: str, body_html: str, parent_id: str | None = None) -> dict[str, Any]:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": self.space},
            "body": {"storage": {"value": body_html, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        r = httpx.post(f"{self.base_url}/rest/api/content", json=payload, auth=self.auth, timeout=20)
        r.raise_for_status()
        d = r.json()
        url = f"{self.base_url}/wiki/spaces/{self.space}/pages/{d['id']}"
        log.info("confluence.publish", title=title, id=d["id"])
        return {"id": d["id"], "title": title, "url": url}


class MockConfluenceAdapter:
    """Captures published pages in memory so the demo can show 'the docs are in Confluence'."""

    pages: list[dict[str, Any]] = []

    def publish(self, *, title: str, body_html: str, parent_id: str | None = None) -> dict[str, Any]:
        pid = uuid.uuid4().hex[:10]
        rec = {
            "id": pid,
            "title": title,
            "url": f"https://hdfcbank.atlassian.net/wiki/spaces/SDLC/pages/{pid}",
            "parent_id": parent_id,
            "mock": True,
        }
        MockConfluenceAdapter.pages.append(rec)
        log.info("confluence.mock.publish", title=title)
        return rec
