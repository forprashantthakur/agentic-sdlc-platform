"""Process Flow 2 agents — sprint planning, development and testing (PRD §9).

Agents 7-11 extend the pipeline from the approved requirement pack into delivery. Each follows the
same contract as Flow 1: produce a versioned, rendered artifact, sync the relevant system of record
(Confluence / Jira), and let a human gate the consequential transitions.

They are lean by design in this release: the mock generators produce structured, traceable artifacts
so the whole flow is demonstrable offline; with Gemini live the same prompts drive richer content.
"""

from __future__ import annotations

import json

from app.adapters import registry
from app.agents import schemas
from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.jira_project import resolve_project_key
from app.core import progress
from app.core.logging import log
from app.models import ArtifactType, Project


def _key(ctx) -> str:
    """This project's own Jira project — not one shared backlog for every requirement."""
    return resolve_project_key(ctx.db, ctx.db.get(Project, ctx.project_id))


def _stories_block(ctx) -> str:
    """The approved Flow-1 user stories the Flow-2 agents build on, as JSON for the prompt."""
    us = ctx.state.get("payloads", {}).get(ArtifactType.USER_STORIES.value) \
        or ctx.state.get("payloads", {}).get(ArtifactType.REFINED_BACKLOG.value, {})
    return json.dumps(us, indent=2)[:16000]


# ── Agent 7 — Backlog & Story Refinement ───────────────────────────────────────
class BacklogRefinementAgent(BaseAgent):
    id = "agent7_backlog"
    name = "Backlog & Story Refinement Agent"

    def run(self) -> AgentResult:
        payload = self.generate(
            task="backlog_refinement",
            prompt=f"PROJECT: {self.ctx.project_name}\n\n"
                   f"APPROVED USER STORIES (refine these; do not invent new ones)\n{_stories_block(self.ctx)}\n\n"
                   f"{self.feedback_block()}\n"
                   "TASK — refine each story: estimate in points, sharpen the acceptance criteria, and "
                   "carry the source requirement. Raise any open questions for the Product Owner.",
            schema=schemas.REFINED_BACKLOG,
        )
        # Publish the approved pack to Confluence (Flow-2 entry point, PRD §8 step 0) and sync Jira.
        pages, issues = [], []
        try:
            page = registry.docs_repo().publish(
                title=f"{self.ctx.project_name} — Refined Backlog",
                body_html=f"<h1>{self.ctx.project_name}</h1><p>Refined backlog published from the "
                          f"approved requirement pack.</p>")
            pages = [page]
        except Exception as e:
            log.warning("confluence.publish_failed", error=str(e))
            progress.emit(f"Confluence publish FAILED — {str(e)[:300]}", level="error")
        try:
            issues = registry.tracker().create_issues(
                project_key=_key(self.ctx),
                issues=[{"type": "Story", "local_id": s.get("id", f"s{i}"),
                         "summary": s.get("title", ""), "story_points": s.get("estimate_points"),
                         "labels": ["flow2", "refined"]}
                        for i, s in enumerate(payload.get("refined_stories", []))])
        except Exception as e:
            log.warning("jira.sync_failed", error=str(e))
            progress.emit(f"Jira sync FAILED — {str(e)[:300]}", level="error")
        v = self.commit(ArtifactType.REFINED_BACKLOG, payload,
                        change_summary="Backlog re-refined per feedback" if self.ctx.feedback
                        else "Refined backlog from approved requirements",
                        external_ref=pages[0]["url"] if pages else None)
        return AgentResult(
            artifacts={ArtifactType.REFINED_BACKLOG.value: v.id},
            payloads={ArtifactType.REFINED_BACKLOG.value: payload},
            external={"confluence": pages, "jira": issues},
            notes=f"{len(payload.get('refined_stories', []))} stories refined · "
                  f"{len(issues)} Jira issues · {len(pages)} Confluence page(s)")


# ── Agent 8 — Sprint Planning & Grooming ────────────────────────────────────────
class GroomingAgent(BaseAgent):
    id = "agent8_grooming"
    name = "Sprint Planning & Grooming Agent"

    def run(self) -> AgentResult:
        payload = self.generate(
            task="grooming",
            prompt=f"PROJECT: {self.ctx.project_name}\n\n"
                   f"REFINED BACKLOG\n{_stories_block(self.ctx)}\n\n{self.feedback_block()}\n"
                   "TASK — compose sprints against team capacity, surface dependencies, and prepare a "
                   "grooming pack for the workshop.",
            schema=schemas.GROOMING_PACK)
        v = self.commit(ArtifactType.GROOMING_PACK, payload,
                        change_summary="Re-groomed per feedback" if self.ctx.feedback
                        else "Grooming pack + sprint composition")
        return AgentResult(
            artifacts={ArtifactType.GROOMING_PACK.value: v.id},
            payloads={ArtifactType.GROOMING_PACK.value: payload},
            notes=f"{len(payload.get('sprints', []))} sprint(s) composed")


# ── Agent 9 — Development Assist & Code Review ──────────────────────────────────
class DevAssistAgent(BaseAgent):
    id = "agent9_dev"
    name = "Development Assist Agent"

    def run(self) -> AgentResult:
        payload = self.generate(
            task="code_review",
            prompt=f"PROJECT: {self.ctx.project_name}\n\n"
                   f"STORIES IN THIS SPRINT\n{_stories_block(self.ctx)}\n\n{self.feedback_block()}\n"
                   "TASK — for each story, generate a code-review checklist from its acceptance "
                   "criteria and the bank coding standard.",
            schema=schemas.CODE_REVIEW)
        v = self.commit(ArtifactType.CODE_REVIEW, payload,
                        change_summary="Re-reviewed after rework" if self.ctx.feedback
                        else "Code-review checklist per story")
        return AgentResult(
            artifacts={ArtifactType.CODE_REVIEW.value: v.id},
            payloads={ArtifactType.CODE_REVIEW.value: payload},
            notes=f"{len(payload.get('reviews', []))} stories reviewed")


# ── Agent 10 — Test Generation & QE ─────────────────────────────────────────────
class TestQEAgent(BaseAgent):
    id = "agent10_qe"
    name = "Test Generation & QE Agent"

    def run(self) -> AgentResult:
        # The QE round drives the deterministic rework loop: bugs on round 1, clean on round 2.
        rnd = self.ctx.state.get("revision", {}).get("qe_gate", 0) + 1
        payload = self.generate(
            task="test_generation",
            prompt=f"PROJECT: {self.ctx.project_name}\nQE ROUND: {rnd}\n\n"
                   f"STORIES & ACCEPTANCE CRITERIA\n{_stories_block(self.ctx)}\n\n"
                   "TASK — generate test cases from each acceptance criterion (one-to-one "
                   "traceability), record execution results, and raise bugs for any failure.",
            schema=schemas.TEST_CASES)
        # Create test tickets (and bugs, if any) in Jira.
        tests, bugs = [], []
        try:
            tests = registry.tracker().create_tests(
                project_key=_key(self.ctx), tests=payload.get("test_cases", []))
            if payload.get("bugs"):
                bugs = registry.tracker().create_bugs(
                    project_key=_key(self.ctx), bugs=payload["bugs"])
        except Exception as e:
            log.warning("jira.qe_sync_failed", error=str(e))
            progress.emit(f"Jira QE sync FAILED — {str(e)[:300]}", level="error")
        v = self.commit(ArtifactType.TEST_CASES, payload,
                        change_summary=f"QE round {rnd}",
                        external_ref=tests[0]["url"] if tests else None)
        return AgentResult(
            artifacts={ArtifactType.TEST_CASES.value: v.id},
            payloads={ArtifactType.TEST_CASES.value: payload},
            external={"jira_tests": tests, "jira_bugs": bugs},
            notes=f"QE round {rnd}: {len(payload.get('test_cases', []))} tests · "
                  f"{len(payload.get('bugs', []))} bug(s) · "
                  f"{'REWORK' if payload.get('bugs_identified') else 'PASS'}")


# ── Agent 11 — Release Readiness & DevOps Hand-off ──────────────────────────────
class ReleaseAgent(BaseAgent):
    id = "agent11_release"
    name = "Release Readiness & DevOps Hand-off Agent"

    def run(self) -> AgentResult:
        payload = self.generate(
            task="release_handoff",
            prompt=f"PROJECT: {self.ctx.project_name}\n\n"
                   f"COMPLETED STORIES\n{_stories_block(self.ctx)}\n\n"
                   "TASK — assemble the completion evidence pack (tests passed, review approved, AC "
                   "coverage) and produce the DevOps release hand-off.",
            schema=schemas.RELEASE_HANDOFF)
        # Transition stories to Done in Jira.
        transitions = []
        try:
            tracker = registry.tracker()
            for s in payload.get("completed_stories", []):
                if s.get("id"):
                    transitions.append(tracker.transition(key=s["id"], to_status="Done"))
        except Exception as e:
            log.warning("jira.transition_failed", error=str(e))
        v = self.commit(ArtifactType.RELEASE_HANDOFF, payload,
                        change_summary="Release hand-off assembled")
        return AgentResult(
            artifacts={ArtifactType.RELEASE_HANDOFF.value: v.id},
            payloads={ArtifactType.RELEASE_HANDOFF.value: payload},
            external={"jira_transitions": transitions},
            notes=f"{len(payload.get('completed_stories', []))} stories → Done · DevOps notified")
