"""Agent 3 — Wireframe Agent.

Two-step by design:
  1. Gemini produces a *structured screen spec* — screens, components, the requirement ids each
     screen satisfies, and a natural-language prompt for the generator.
  2. A wireframe provider turns that spec into real screens.

The provider is pluggable (WIREFRAME_PROVIDER):

  * **Google Stitch** (default) generates a screen FROM TEXT and returns HTML plus a screenshot.
    That is an exact match for what this agent already produces, and the screenshot can be embedded
    in the BRD itself rather than hidden behind a link only seat-holders can open.
  * **Figma** draws frames in a Figma file. It wants geometry, and write-to-canvas needs a Full seat
    on a paid plan.

Keeping the spec separate from the drawing is what makes this safe: the wireframe stays reviewable
and diffable *as data*, Agent 4 consumes the spec (not the picture), and a provider outage degrades
to "spec produced, screens pending" rather than a failed run.
"""

from __future__ import annotations

import json

from app.adapters import registry
from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import WIREFRAME
from app.core.config import settings
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
- `stitch_prompt`: a plain-English description of the screen for a UI generator — what it is for,
  who uses it, what they can do, and what happens when things go wrong. Two or three sentences.
  Write it for a generator that has not read the requirements, because it has not.
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
            external = registry.wireframer().create_wireframes(
                project_name=self.ctx.project_name,
                screens=spec["screens"],
                design_system=spec.get("design_system", "HDFC MobileBanking DS v4"),
            )
            spec["wireframes"] = external
        except Exception as e:
            # The provider is never allowed to fail the run. The spec is the artifact Agent 4
            # consumes; the rendered screens are for humans to look at.
            log.error("wireframe.provider_failed", provider=settings.wireframe_provider, error=str(e))
            spec["wireframes"] = {"provider": settings.wireframe_provider, "error": str(e),
                                  "status": "SCREENS_PENDING"}

        link = external.get("project_url") or external.get("file_url")
        v = self.commit(
            ArtifactType.WIREFRAME,
            spec,
            change_summary="Wireframes regenerated per feedback" if self.ctx.feedback
                           else f"Initial wireframe spec + {settings.wireframe_provider} screens",
            external_ref=link,
        )
        return AgentResult(
            artifacts={ArtifactType.WIREFRAME.value: v.id},
            payloads={ArtifactType.WIREFRAME.value: spec},
            external=external,
            notes=(f"{len(spec.get('screens', []))} screens → "
                   f"{settings.wireframe_provider}: {link or 'pending'}"),
        )
