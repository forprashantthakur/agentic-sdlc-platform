"""Agent 2 — Concept Note Generator.

The concept note is the first document a business sponsor actually reads, and it is the
first approval gate. It converts requirements into a decision-ready framing: objectives,
scope, an explicit out-of-scope list, business rules, assumptions, dependencies, risks.

The out-of-scope list is doing the heavy lifting — most banking-project overruns are
scope that was never explicitly excluded.
"""

from __future__ import annotations

import json

from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import CONCEPT_NOTE
from app.models import ArtifactType

PROMPT = """PROJECT: {project}

APPROVED BUSINESS REQUIREMENTS
{requirements}

{recall}

{feedback}

TASK — produce a Concept Note that a business sponsor and a compliance officer can approve.

- business_objectives: outcome-based and measurable. "Reduce X by N% within M months", not "improve X".
- scope: what this release delivers, phrased so an engineer could not misread it.
- out_of_scope: be aggressive and explicit. Everything a reader might *assume* is included but
  is not, belongs here. This list prevents the scope creep that kills bank programmes.
- business_rules: the decision logic (thresholds, limits, state transitions), each with an id.
  Encode any regulatory threshold you find in the requirements.
- assumptions: what must hold for the plan to work. Every assumption is a latent risk.
- dependencies: internal / external / regulatory / vendor, with the impact if the dependency slips.
- risks: likelihood × impact with a concrete mitigation. No "monitor closely" non-mitigations.

Carry the requirement conflicts and gaps forward into risks or assumptions — do not silently drop them.
"""


class ConceptNoteAgent(BaseAgent):
    id = "agent2_concept_note"
    name = "Concept Note Agent"

    def run(self) -> AgentResult:
        reqs = self.ctx.state.get("payloads", {}).get(ArtifactType.BUSINESS_REQUIREMENTS.value, {})

        payload = self.generate(
            task="concept_note",
            prompt=PROMPT.format(
                project=self.ctx.project_name,
                requirements=json.dumps(reqs, indent=2)[:24000],
                recall=self.recall(
                    "regulatory constraints, business rules and risks relevant to this capability",
                    namespaces=["source", "org_standard"],
                ),
                feedback=self.feedback_block(),
            ),
            schema=CONCEPT_NOTE,
            temperature=0.25,
        )

        v = self.commit(
            ArtifactType.CONCEPT_NOTE,
            payload,
            change_summary="Revised per reviewer comments" if self.ctx.feedback else "Initial concept note",
        )
        return AgentResult(
            artifacts={ArtifactType.CONCEPT_NOTE.value: v.id},
            payloads={ArtifactType.CONCEPT_NOTE.value: payload},
            notes=(
                f"{len(payload.get('business_rules', []))} business rules · "
                f"{len(payload.get('risks', []))} risks · "
                f"{len(payload.get('out_of_scope', []))} explicit exclusions"
            ),
        )
