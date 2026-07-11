"""Ports (interfaces) for every external system.

Agents depend only on these protocols. That is what keeps the graph unit-testable and
lets the whole platform boot with an empty .env: `registry.py` hands back a Mock*
implementation whenever credentials are absent or MOCK_MODE is on.
"""

from __future__ import annotations

from typing import Any, Protocol


class FigmaPort(Protocol):
    def create_wireframes(
        self, *, project_name: str, screens: list[dict[str, Any]], design_system: str
    ) -> dict[str, Any]:
        """Returns {file_key, file_url, frames: [name], thumbnails: [url]}."""


class MailPort(Protocol):
    def send(
        self, *, to: list[str], subject: str, html: str, thread_id: str | None = None
    ) -> dict[str, Any]:
        """Returns {message_id, thread_id}."""

    def fetch_replies(self, *, thread_id: str) -> list[dict[str, Any]]:
        """Returns [{from, body, received_at}]."""


class DrivePort(Protocol):
    def upload_markdown(
        self, *, folder: str, name: str, markdown: str
    ) -> dict[str, Any]:
        """Returns {file_id, url}."""


class TrackerPort(Protocol):
    def create_issues(self, *, project_key: str, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Returns [{key, url, type, summary}] in the same order as `issues`."""
