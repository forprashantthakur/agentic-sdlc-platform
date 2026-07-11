"""Jira — the sprint agent's write target.

Issues are created parent-first (Epic → Story) so the `parent` link resolves. Every
issue carries the requirement ids in a label, which is what makes end-to-end
traceability (meeting note → requirement → story → Jira ticket) actually queryable.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.logging import log


class JiraAdapter:
    def __init__(self, base_url: str, email: str, token: str) -> None:
        self.base = base_url.rstrip("/")
        self.auth = (email, token)

    def create_issues(self, *, project_key, issues) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        key_by_local: dict[str, str] = {}

        # Epics first, so stories can reference a real parent key.
        for issue in sorted(issues, key=lambda i: 0 if i["type"] == "Epic" else 1):
            fields: dict[str, Any] = {
                "project": {"key": project_key},
                "summary": issue["summary"],
                "issuetype": {"name": issue["type"]},
                "description": _adf(issue.get("description", "")),
                "labels": ["agentic-sdlc", *issue.get("labels", [])],
            }
            if issue["type"] == "Story":
                if sp := issue.get("story_points"):
                    fields["customfield_10016"] = sp  # story points field id varies by instance
                if parent_local := issue.get("parent_local_id"):
                    if pk := key_by_local.get(parent_local):
                        fields["parent"] = {"key": pk}

            with httpx.Client(timeout=45) as c:
                r = c.post(f"{self.base}/rest/api/3/issue", json={"fields": fields}, auth=self.auth)
                r.raise_for_status()
                data = r.json()

            key_by_local[issue["local_id"]] = data["key"]
            created.append({
                "key": data["key"], "url": f"{self.base}/browse/{data['key']}",
                "type": issue["type"], "summary": issue["summary"],
            })
        return created


def _adf(text: str) -> dict[str, Any]:
    """Jira Cloud v3 wants Atlassian Document Format, not a plain string."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line or " "}]}
            for line in text.split("\n")
        ],
    }


class MockJiraAdapter:
    issues: list[dict[str, Any]] = []
    _counter = 1000

    def create_issues(self, *, project_key, issues) -> list[dict[str, Any]]:
        out = []
        for issue in sorted(issues, key=lambda i: 0 if i["type"] == "Epic" else 1):
            MockJiraAdapter._counter += 1
            key = f"{project_key}-{MockJiraAdapter._counter}"
            rec = {
                "key": key, "url": f"https://hdfcbank.atlassian.net/browse/{key}",
                "type": issue["type"], "summary": issue["summary"],
                "story_points": issue.get("story_points"), "labels": issue.get("labels", []),
            }
            MockJiraAdapter.issues.append(rec)
            out.append(rec)
        log.info("jira.mock.create", count=len(out), project=project_key)
        return out
