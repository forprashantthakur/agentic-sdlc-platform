"""Agent 3 — Wireframe Agent (Figma over MCP).

Two-step by design:
  1. Gemini produces a *structured screen spec* — screens, components, and the requirement
     ids each screen satisfies.
  2. The Figma MCP adapter turns that spec into real frames.

Keeping the spec separate from the drawing means the wireframe is reviewable and diffable
as data, and a Figma outage degrades to "spec produced, frames pending" rather than a
failed run.
"""

from __future__ import annotations

import json

from app.adapters import registry
from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import WIREFRAME
from app.core.logging import log
from app.models import ArtifactType

PROMPT = """PROJECT: {project}

APPROVED CONCEPT NOTE
{concept}

BUSINESS REQUIREMENTS
{requirements}

{feedback}

TASK — specify low-fidelity wireframes for the customer-facing journey.

- One screen per meaningful state, including empty states, error states and confirmation states.
  Junior specs only cover the happy path; yours must not.
- For each component give a semantic `type` (AppBar, PrimaryButton, AmountField, MPINPad,
  InlineAlert, EmptyState, StatusPill, ...), a `label`, and `props` that pin down behaviour
  (validation, visibility conditions, limits).
- `requirement_ids` on every screen: a screen that traces to no requirement should not exist.
- `flow`: the navigation path through the screens.
- Assume the HDFC MobileBanking design system and mobile-first (375pt) layout.
"""


class WireframeAgent(BaseAgent):
    id = "agent3_wireframe"
    name = "Wireframe Agent"

    def run(self) -> AgentResult:
        payloads = self.ctx.state.get("payloads", {})
        spec = self.generate(
            task="wireframe",
            prompt=PROMPT.format(
                project=self.ctx.project_name,
                concept=json.dumps(payloads.get(ArtifactType.CONCEPT_NOTE.value, {}), indent=2)[:16000],
                requirements=json.dumps(payloads.get(ArtifactType.BUSINESS_REQUIREMENTS.value, {}), indent=2)[:12000],
                feedback=self.feedback_block(),
            ),
            schema=WIREFRAME,
            temperature=0.35,
        )

        external = {}
        try:
            external = registry.figma().create_wireframes(
                project_name=self.ctx.project_name,
                screens=spec["screens"],
                design_system=spec.get("design_system", "HDFC MobileBanking DS v4"),
            )
            spec["figma"] = external
        except Exception as e:  # Figma is not allowed to fail the run
            log.error("figma.failed", error=str(e))
            spec["figma"] = {"error": str(e), "status": "FRAMES_PENDING"}

        v = self.commit(
            ArtifactType.WIREFRAME,
            spec,
            change_summary="Wireframes regenerated per feedback" if self.ctx.feedback else "Initial wireframe spec + Figma frames",
            external_ref=external.get("file_url"),
        )
        return AgentResult(
            artifacts={ArtifactType.WIREFRAME.value: v.id},
            payloads={ArtifactType.WIREFRAME.value: spec},
            external=external,
            notes=f"{len(spec.get('screens', []))} screens → Figma: {external.get('file_url', 'pending')}",
        )
