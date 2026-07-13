"""Agent 4 — Requirement Document Agent.

Produces the full documentation set from the approved concept note and wireframes:
BRD, FRD, SRS, User Stories, Acceptance Criteria, API Requirements, NFRs.

Each document is a *separate* generation with its own schema and its own artifact/version
lineage. That matters: an FRD revision after a review comment must not silently rewrite the
approved BRD. It also means a failure in one document doesn't lose the other six.

Acceptance Criteria are derived from the user stories rather than generated independently,
so the two can never drift apart.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import API_REQUIREMENTS, DOCUMENT, NFR, USER_STORIES
from app.core.config import settings
from app.models import ArtifactType

DOC_PROMPT = """PROJECT: {project}

APPROVED CONCEPT NOTE
{concept}

BUSINESS REQUIREMENTS
{requirements}

WIREFRAME SPEC
{wireframes}

{recall}

{feedback}

TASK — write the {doc_type}.

{guidance}

Every section must be substantive prose an engineer or auditor can act on. Populate the
`traceability` array mapping every BR-xxx id to the section that satisfies it. If a
requirement is not covered anywhere in this document, that is a defect — cover it.
"""

GUIDANCE = {
    "BRD": """A Business Requirements Document for a bank sponsor and a compliance officer.
Sections: Executive Summary; Business Context & Problem Statement; Business Objectives; Scope;
Stakeholders; Business Requirements; Business Rules; Assumptions, Dependencies & Risks;
Success Metrics; Regulatory Considerations (RBI, data localisation, audit retention).
Write for a reader who controls budget, not for an engineer.""",

    "FRD": """A Functional Requirements Document. Decompose the BRD into implementable behaviour.
Sections: Purpose; Actors & Roles; one section per functional requirement (FR-01, FR-02, ...)
written in GIVEN/WHEN/THEN or SHALL form with explicit state machines where state exists;
Error Handling (every external error code mapped to a customer-safe message); Audit & Logging.
Be pedantic about state transitions and edge cases.""",

    "SRS": """A Software Requirements Specification, IEEE-830 flavoured, for the engineering team.
Sections: Introduction (purpose, scope, definitions); Overall Description (product perspective,
user classes, constraints); System Architecture (components, protocols, async topics);
Data Model (tables and key columns); External Interfaces; Non-Functional Requirements (reference
the NFR artifact); Verification. Be concrete about technology and integration boundaries.""",
}

STORIES_PROMPT = """PROJECT: {project}

CONCEPT NOTE
{concept}

BUSINESS REQUIREMENTS
{requirements}

WIREFRAMES
{wireframes}

{feedback}

TASK — write INVEST-compliant user stories.
- Each story: as_a / i_want / so_that, traced to requirement ids.
- 2-4 acceptance criteria per story, in GIVEN/WHEN/THEN form, each independently testable and
  containing a concrete threshold or observable outcome (no "works correctly").
- Fibonacci story points (1,2,3,5,8,13). Size integration-heavy stories honestly — a story that
  touches an external switch is not a 3.
- Cover the non-happy paths and the compliance/audit stories, not just the customer journey.
"""

API_PROMPT = """PROJECT: {project}

FRD
{frd}

WIREFRAMES
{wireframes}

{recall}

{feedback}

TASK — specify the API surface required to deliver this capability.
Every mutating endpoint must state its auth model, idempotency behaviour, error codes and a
latency SLA. Follow bank API conventions: REST/JSON, RFC 7807 errors, mandatory Idempotency-Key
on mutations, X-Correlation-Id propagation, path versioning. Include internal/callback endpoints
(e.g. switch-initiated callbacks) with their mTLS/signature requirements.
"""

NFR_PROMPT = """PROJECT: {project}

CONCEPT NOTE
{concept}

FRD
{frd}

{recall}

{feedback}

TASK — specify Non-Functional Requirements across, at minimum: Performance, Scalability,
Availability, Security, Compliance, Data Residency, Observability, Accessibility, Resilience.

Every NFR must be measurable and must state HOW it is measured. "Highly available" is rejected;
"99.95% monthly availability measured as a Prometheus SLO with an error-budget policy" is accepted.
Include the RBI data-localisation and audit-retention requirements — this is an Indian bank.
"""


class RequirementDocumentAgent(BaseAgent):
    id = "agent4_requirement_docs"
    name = "Requirement Document Agent"

    def run(self) -> AgentResult:
        p = self.ctx.state.get("payloads", {})
        concept = json.dumps(p.get(ArtifactType.CONCEPT_NOTE.value, {}), indent=2)[:16000]
        reqs = json.dumps(p.get(ArtifactType.BUSINESS_REQUIREMENTS.value, {}), indent=2)[:12000]
        wires = json.dumps(p.get(ArtifactType.WIREFRAME.value, {}), indent=2)[:8000]
        recall = self.recall(
            "bank API conventions, NFR baselines, RBI regulatory constraints",
            namespaces=["org_standard", "source"],
        )
        fb = self.feedback_block()

        def doc(doc_type: str) -> dict:
            return self.generate(
                task=doc_type.lower(),
                prompt=DOC_PROMPT.format(
                    project=self.ctx.project_name, concept=concept, requirements=reqs,
                    wireframes=wires, recall=recall, feedback=fb,
                    doc_type=doc_type, guidance=GUIDANCE[doc_type],
                ),
                schema=DOCUMENT,
                temperature=0.25,
            )

        # BRD / FRD / SRS are independent, so they *can* run concurrently — but firing three
        # (plus three more below) at a free-tier quota is the surest way to earn a 429 or a 503.
        # Concurrency is a throughput optimisation; a failed run is not a throughput problem.
        workers = 3 if settings.gemini_concurrency > 1 else 1
        with ThreadPoolExecutor(max_workers=min(workers, settings.gemini_concurrency)) as ex:
            brd, frd, srs = ex.map(doc, ["BRD", "FRD", "SRS"])

        frd_json = json.dumps(frd, indent=2)[:16000]

        stories = self.generate(
            task="user_stories",
            prompt=STORIES_PROMPT.format(
                project=self.ctx.project_name, concept=concept, requirements=reqs,
                wireframes=wires, feedback=fb,
            ),
            schema=USER_STORIES, temperature=0.3,
        )
        apis = self.generate(
            task="api_requirements",
            prompt=API_PROMPT.format(
                project=self.ctx.project_name, frd=frd_json, wireframes=wires,
                recall=recall, feedback=fb,
            ),
            schema=API_REQUIREMENTS, temperature=0.2,
        )
        nfrs = self.generate(
            task="nfr",
            prompt=NFR_PROMPT.format(
                project=self.ctx.project_name, concept=concept, frd=frd_json,
                recall=recall, feedback=fb,
            ),
            schema=NFR, temperature=0.2,
        )

        bundle = {
            ArtifactType.BRD: brd,
            ArtifactType.FRD: frd,
            ArtifactType.SRS: srs,
            ArtifactType.USER_STORIES: stories,
            ArtifactType.ACCEPTANCE_CRITERIA: stories,  # derived view — cannot drift from the stories
            ArtifactType.API_REQUIREMENTS: apis,
            ArtifactType.NFR: nfrs,
        }

        artifacts: dict[str, str] = {}
        payloads: dict[str, dict] = {}
        for atype, payload in bundle.items():
            v = self.commit(
                atype, payload,
                change_summary="Regenerated per reviewer comments" if self.ctx.feedback else "Initial generation",
            )
            artifacts[atype.value] = v.id
            payloads[atype.value] = payload

        coverage = self._coverage(p.get(ArtifactType.BUSINESS_REQUIREMENTS.value, {}), brd, frd, srs, stories)
        return AgentResult(
            artifacts=artifacts,
            payloads=payloads,
            notes=(
                f"BRD/FRD/SRS + {len(stories.get('stories', []))} stories, "
                f"{len(apis.get('endpoints', []))} endpoints, {len(nfrs.get('nfrs', []))} NFRs · "
                f"requirement coverage {coverage}"
            ),
        )

    @staticmethod
    def _coverage(reqs: dict, *docs: dict) -> str:
        """Traceability check — the cheapest, highest-value guardrail in the whole platform."""
        ids = {r["id"] for r in reqs.get("requirements", [])}
        if not ids:
            return "n/a"
        covered: set[str] = set()
        for d in docs:
            for t in d.get("traceability", []) or []:
                covered.add(t.get("requirement_id", ""))
            for s in d.get("stories", []) or []:
                covered.update(s.get("requirement_ids", []))
        hit = len(ids & covered)
        return f"{hit}/{len(ids)}" + ("" if hit == len(ids) else f" (UNCOVERED: {', '.join(sorted(ids - covered))})")
