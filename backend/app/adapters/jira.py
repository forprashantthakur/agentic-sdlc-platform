"""Jira — the sprint agent's write target.

Issues are created parent-first (Epic → Story) so the `parent` link resolves. Every
issue carries the requirement ids in a label, which is what makes end-to-end
traceability (meeting note → requirement → story → Jira ticket) actually queryable.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core import progress
from app.core.config import settings
from app.core.logging import log


class JiraAdapter:
    def __init__(self, base_url: str, email: str, token: str) -> None:
        self.base = base_url.rstrip("/")
        self.auth = (email, token)
        self._types: list[str] | None = None      # the project's real issue types
        self._sp_field: str | None = None         # the project's real story-points field

    # ── instance introspection ────────────────────────────────────────────────
    def _project_types(self, project_key: str) -> list[str]:
        """The issue types this project actually has.

        Jira templates differ wildly: a business/finance project has Epic, Task, Subtask,
        Allocation, Expense Request — and no Story or Bug at all. Asking for a type the project
        does not define is a 400 that would fail the whole run, so we look first.
        """
        if self._types is not None:
            return self._types
        try:
            with httpx.Client(timeout=20, auth=self.auth) as c:
                r = c.get(f"{self.base}/rest/api/3/project/{project_key}")
                r.raise_for_status()
                self._types = [t["name"] for t in r.json().get("issueTypes", [])]
        except Exception as e:
            log.warning("jira.types_lookup_failed", error=str(e))
            self._types = []
        return self._types

    def _resolve_type(self, wanted: str, project_key: str) -> str:
        """Map a wanted type onto one the project has, falling back to Task.

        Creating a Task named "As a treasurer, I want…" is a lesser evil than failing the run:
        the work still lands in the backlog, traceable, and the summary carries the story text.
        """
        types = self._project_types(project_key)
        if not types or wanted in types:
            return wanted
        for alt in ("Task", "Story", types[0]):
            if alt in types:
                log.info("jira.type_fallback", wanted=wanted, used=alt)
                return alt
        return wanted

    def _story_points_field(self) -> str | None:
        """Configured field, else auto-detected, else None (estimates simply are not written)."""
        if settings.jira_story_points_field:
            return settings.jira_story_points_field
        if self._sp_field is not None:
            return self._sp_field or None
        try:
            with httpx.Client(timeout=20, auth=self.auth) as c:
                r = c.get(f"{self.base}/rest/api/3/field")
                r.raise_for_status()
                match = next((f["id"] for f in r.json()
                              if "story point" in (f.get("name") or "").lower()
                              and str(f.get("id", "")).startswith("customfield")), "")
                self._sp_field = match
        except Exception as e:
            log.warning("jira.field_lookup_failed", error=str(e))
            self._sp_field = ""
        return self._sp_field or None

    def find_project(self, key: str) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=20, auth=self.auth) as c:
                r = c.get(f"{self.base}/rest/api/3/project/{key}")
                if r.status_code == 200:
                    d = r.json()
                    return {"key": d["key"], "name": d.get("name", ""),
                            "url": f"{self.base}/browse/{d['key']}", "created": False}
        except Exception as e:
            log.warning("jira.find_project_failed", key=key, error=str(e))
        return None

    def create_project(self, *, key: str, name: str) -> dict[str, Any]:
        """Create a Scrum software project.

        Deliberately the SCRUM SOFTWARE template: it ships with Story, Bug and story points, which
        a business/finance template does not — so auto-provisioning also gives the agents the issue
        types they actually want, instead of falling back to Task.

        Creating projects needs Jira admin rights. If the account lacks them this raises, and the
        caller falls back to the configured project rather than failing the run.
        """
        with httpx.Client(timeout=45, auth=self.auth) as c:
            me = c.get(f"{self.base}/rest/api/3/myself")
            me.raise_for_status()
            lead = me.json()["accountId"]
            body = {
                "key": key,
                "name": name[:80],
                "projectTypeKey": "software",
                "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum",
                "leadAccountId": lead,
                "assigneeType": "PROJECT_LEAD",
                "description": "Auto-created by the HDFC Agentic SDLC Platform.",
            }
            r = c.post(f"{self.base}/rest/api/3/project", json=body)
            if r.status_code >= 300:
                raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
            d = r.json()
        log.info("jira.project_created", key=key, name=name)
        return {"key": d.get("key", key), "name": name,
                "url": f"{self.base}/browse/{d.get('key', key)}", "created": True}

    def create_issues(self, *, project_key, issues) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        key_by_local: dict[str, str] = {}

        # Epics first, so stories can reference a real parent key.
        for issue in sorted(issues, key=lambda i: 0 if i["type"] == "Epic" else 1):
            fields: dict[str, Any] = {
                "project": {"key": project_key},
                "summary": issue["summary"],
                "issuetype": {"name": self._resolve_type(issue["type"], project_key)},
                "description": _adf(issue.get("description", "")),
                "labels": ["agentic-sdlc", *issue.get("labels", [])],
            }
            if issue["type"] == "Story":
                # Only write points if this instance actually has the field; otherwise Jira 400s
                # on an unknown field and the whole issue is lost for the sake of an estimate.
                if (sp := issue.get("story_points")) and (spf := self._story_points_field()):
                    fields[spf] = sp
                if parent_local := issue.get("parent_local_id"):
                    if pk := key_by_local.get(parent_local):
                        fields["parent"] = {"key": pk}

            with httpx.Client(timeout=45) as c:
                data = self._post_issue(c, fields)

            key_by_local[issue["local_id"]] = data["key"]
            created.append({
                "key": data["key"], "url": f"{self.base}/browse/{data['key']}",
                "type": issue["type"], "summary": issue["summary"],
            })
        return created

    def find_project(self, key: str) -> dict[str, Any] | None:
        return {"key": key, "name": key, "mock": True,
                "url": f"https://hdfcbank.atlassian.net/browse/{key}", "created": False}

    def create_project(self, *, key: str, name: str) -> dict[str, Any]:
        log.info("jira.mock.project_created", key=key, name=name)
        return {"key": key, "name": name, "mock": True,
                "url": f"https://hdfcbank.atlassian.net/jira/software/projects/{key}/boards/1",
                "created": True}

    @staticmethod
    def _jira_error(r) -> str:
        """Jira puts the real reason in the BODY. raise_for_status() throws it away, which is how a
        400 becomes '400 Bad Request' and tells you nothing about which field it rejected."""
        try:
            d = r.json()
            parts = list(d.get("errorMessages") or [])
            parts += [f"{k}: {v}" for k, v in (d.get("errors") or {}).items()]
            return "; ".join(parts) or r.text[:300]
        except Exception:
            return r.text[:300]

    # Fields Jira may legitimately reject depending on project type and configuration. Dropping
    # them costs metadata; keeping them costs the whole issue.
    _OPTIONAL = ("parent", "labels", "customfield_10016")

    def _post_issue(self, c, fields: dict[str, Any]) -> dict[str, Any]:
        r = c.post(f"{self.base}/rest/api/3/issue", json={"fields": fields}, auth=self.auth)
        if r.status_code < 300:
            return r.json()
        detail = self._jira_error(r)

        # A 400 is usually one unsupported field, not a broken request. Retry once with the
        # optional ones removed rather than losing the story entirely — and say what was dropped.
        if r.status_code == 400:
            slim = {k: v for k, v in fields.items()
                    if k not in self._OPTIONAL and not k.startswith("customfield_")}
            r2 = c.post(f"{self.base}/rest/api/3/issue", json={"fields": slim}, auth=self.auth)
            if r2.status_code < 300:
                dropped = sorted(set(fields) - set(slim))
                log.warning("jira.created_without_fields", dropped=dropped, reason=detail[:200])
                progress.emit(
                    f"Jira accepted the issue only after dropping {', '.join(dropped)} — {detail[:160]}",
                    level="warning")
                return r2.json()
            detail = f"{detail} | retry without {self._OPTIONAL}: {self._jira_error(r2)}"

        raise RuntimeError(f"Jira {r.status_code}: {detail}")

    def create_tests(self, *, project_key, tests) -> list[dict[str, Any]]:
        return self.create_issues(project_key=project_key, issues=[
            {"type": "Test", "local_id": f"t{i}", "summary": t.get("title", ""),
             "description": t.get("steps", ""), "labels": ["qe", f"story-{t.get('story_id','')}"]}
            for i, t in enumerate(tests)])

    def create_bugs(self, *, project_key, bugs) -> list[dict[str, Any]]:
        return self.create_issues(project_key=project_key, issues=[
            {"type": "Bug", "local_id": f"b{i}", "summary": b.get("title", ""),
             "description": b.get("detail", ""), "labels": ["qe-bug", f"story-{b.get('story_id','')}"]}
            for i, b in enumerate(bugs)])

    def transition(self, *, key, to_status) -> dict[str, Any]:
        # Real transitions need the instance's transition id; this is best-effort and never fatal.
        try:
            with httpx.Client(timeout=30) as c:
                tr = c.get(f"{self.base}/rest/api/3/issue/{key}/transitions", auth=self.auth).json()
                match = next((t for t in tr.get("transitions", [])
                              if t["to"]["name"].lower() == to_status.lower()), None)
                if match:
                    c.post(f"{self.base}/rest/api/3/issue/{key}/transitions",
                           json={"transition": {"id": match["id"]}}, auth=self.auth)
        except Exception as e:  # a transition failure must not fail the run
            log.warning("jira.transition_failed", key=key, error=str(e))
        return {"key": key, "status": to_status, "url": f"{self.base}/browse/{key}"}


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

    def find_project(self, key: str) -> dict[str, Any] | None:
        return {"key": key, "name": key, "mock": True,
                "url": f"https://hdfcbank.atlassian.net/browse/{key}", "created": False}

    def create_project(self, *, key: str, name: str) -> dict[str, Any]:
        log.info("jira.mock.project_created", key=key, name=name)
        return {"key": key, "name": name, "mock": True,
                "url": f"https://hdfcbank.atlassian.net/jira/software/projects/{key}/boards/1",
                "created": True}

    def create_tests(self, *, project_key, tests) -> list[dict[str, Any]]:
        out = []
        for t in tests:
            MockJiraAdapter._counter += 1
            key = f"{project_key}-{MockJiraAdapter._counter}"
            out.append({"key": key, "url": f"https://hdfcbank.atlassian.net/browse/{key}",
                        "type": "Test", "summary": t.get("title", ""), "story_id": t.get("story_id")})
        log.info("jira.mock.tests", count=len(out))
        return out

    def create_bugs(self, *, project_key, bugs) -> list[dict[str, Any]]:
        out = []
        for b in bugs:
            MockJiraAdapter._counter += 1
            key = f"{project_key}-{MockJiraAdapter._counter}"
            out.append({"key": key, "url": f"https://hdfcbank.atlassian.net/browse/{key}",
                        "type": "Bug", "summary": b.get("title", ""), "story_id": b.get("story_id"),
                        "severity": b.get("severity", "Medium")})
        log.info("jira.mock.bugs", count=len(out))
        return out

    def transition(self, *, key, to_status) -> dict[str, Any]:
        log.info("jira.mock.transition", key=key, to=to_status)
        return {"key": key, "status": to_status,
                "url": f"https://hdfcbank.atlassian.net/browse/{key}"}
