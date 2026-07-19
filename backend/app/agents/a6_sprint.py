"""Agent 6 — Sprint Agent.

Turns the approved documentation set into an executable backlog: epics → features →
stories → story points → acceptance criteria, then writes it into Jira.

It re-uses the user stories the Requirement Document Agent already produced rather than
inventing new ones. Re-generating stories here would break traceability to the approved
BRD — the backlog must be the *same* stories, just organised for delivery.
"""

from __future__ import annotations

import json

from app.adapters import registry
from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import SPRINT_PLAN
from app.core.config import settings
from app.services.jira_project import resolve_project_key
from app.core.logging import log
from app.models import ArtifactType, Project

PROMPT = """PROJECT: {project}

APPROVED USER STORIES (these are fixed — organise them, do not rewrite them)
{stories}

APPROVED CONCEPT NOTE (for risks and dependencies)
{concept}

NON-FUNCTIONAL REQUIREMENTS
{nfrs}

{feedback}

TASK — produce a delivery plan.
1. Group the stories into epics and features. Every story id must appear in exactly one feature.
2. Sequence the stories into sprints. Respect dependencies: a story cannot precede the story it
   depends on, and external-dependency stories (e.g. anything needing NPCI certification) must be
   scheduled early enough to absorb slippage.
3. Assume the velocity given below; do not overfill a sprint.
4. Per sprint, state a single-sentence sprint goal and any risks that could sink it.
5. In estimation_notes, explain the sizing rationale for the largest story.

Velocity assumption: {velocity} points per sprint.
"""


class SprintAgent(BaseAgent):
    id = "agent6_sprint"
    name = "Sprint Agent"

    def __init__(self, ctx, velocity: int = 15) -> None:
        super().__init__(ctx)
        self.velocity = velocity

    def run(self) -> AgentResult:
        p = self.ctx.state.get("payloads", {})
        stories = p.get(ArtifactType.USER_STORIES.value, {})

        plan = self.generate(
            task="sprint_plan",
            prompt=PROMPT.format(
                project=self.ctx.project_name,
                stories=json.dumps(stories, indent=2)[:20000],
                concept=json.dumps(p.get(ArtifactType.CONCEPT_NOTE.value, {}), indent=2)[:8000],
                nfrs=json.dumps(p.get(ArtifactType.NFR.value, {}), indent=2)[:6000],
                feedback=self.feedback_block(),
                velocity=self.velocity,
            ),
            schema=SPRINT_PLAN,
            temperature=0.25,
        )
        plan.setdefault("velocity_assumption", self.velocity)

        issues = self._to_jira_issues(plan, stories)
        try:
            created = registry.tracker().create_issues(
                project_key=resolve_project_key(self.ctx.db, self.ctx.db.get(Project, self.ctx.project_id)),
                issues=issues
            )
            plan["jira"] = created
        except Exception as e:  # a Jira outage must not lose the plan
            log.error("jira.failed", error=str(e))
            plan["jira"] = []
            plan["jira_error"] = str(e)
            created = []

        v = self.commit(
            ArtifactType.SPRINT_PLAN, plan,
            change_summary="Re-planned per feedback" if self.ctx.feedback else "Initial sprint plan + Jira backlog",
            external_ref=created[0]["url"] if created else None,
        )
        total = sum(s.get("points", 0) for s in plan.get("sprints", []))
        return AgentResult(
            artifacts={ArtifactType.SPRINT_PLAN.value: v.id},
            payloads={ArtifactType.SPRINT_PLAN.value: plan},
            external={"jira": created},
            notes=(
                f"{len(plan.get('epics', []))} epics · {len(plan.get('sprints', []))} sprints · "
                f"{total} points · {len(created)} Jira issues created"
            ),
        )

    def _to_jira_issues(self, plan: dict, stories: dict) -> list[dict]:
        by_id = {s["id"]: s for s in stories.get("stories", [])}
        sprint_of = {
            sid: sp["number"] for sp in plan.get("sprints", []) for sid in sp.get("story_ids", [])
        }
        issues: list[dict] = []

        for ep in plan.get("epics", []):
            issues.append({
                "local_id": ep["id"], "type": "Epic",
                "summary": f"{ep['id']} {ep['name']}",
                "description": ep.get("goal", ""),
                "labels": ["epic"],
            })
            for feat in ep.get("features", []):
                for sid in feat.get("story_ids", []):
                    st = by_id.get(sid)
                    if not st:
                        continue
                    ac = "\n".join(f"AC{i}: {c}" for i, c in enumerate(st.get("acceptance_criteria", []), 1))
                    issues.append({
                        "local_id": sid, "type": "Story", "parent_local_id": ep["id"],
                        "summary": f"{sid} As a {st['as_a']}, I want {st['i_want']}",
                        "description": (
                            f"As a {st['as_a']}\nI want {st['i_want']}\nSo that {st['so_that']}\n\n"
                            f"Feature: {feat['id']} {feat['name']}\n"
                            f"Sprint: {sprint_of.get(sid, 'backlog')}\n\n"
                            f"Acceptance Criteria\n{ac}\n\n"
                            f"Traces to: {', '.join(st.get('requirement_ids', []))}"
                        ),
                        "story_points": st.get("story_points"),
                        "labels": [f"sprint-{sprint_of.get(sid, 'backlog')}", *st.get("requirement_ids", [])],
                    })
        return issues
