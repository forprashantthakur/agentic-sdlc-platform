"""Agent 1 — Requirement Gathering.

In:  meeting notes, emails, voice transcripts (already ingested as Sources and indexed
     into the `source` namespace of long-term memory).
Out: structured, evidence-linked business requirements + stakeholders + conflicts + gaps.

The gaps and conflicts are the point. An agent that quietly resolves an ambiguity is a
liability; an agent that escalates it is an analyst.
"""

from __future__ import annotations

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import REQUIREMENTS
from app.memory import rag
from app.models import ArtifactType, Source

PROMPT = """PROJECT: {project}

You are extracting business requirements for a new capability at HDFC Bank.

Below is the complete raw evidence base — meeting notes, email threads and voice
transcripts from discovery. Read all of it.

{sources}

{recall}

{feedback}

TASK
1. Extract every distinct business requirement. Give each a stable id (BR-001, BR-002, ...).
2. For each requirement cite the specific evidence it came from in `source_evidence`
   (name the source and the line/timestamp). A requirement with no citation is a hallucination —
   do not emit it.
3. Set `confidence` honestly: 0.9+ only when the evidence is explicit and unambiguous.
4. Identify stakeholders and their roles.
5. Where two sources disagree, emit a `conflict` naming the requirement ids and who must resolve it.
   Do NOT resolve it yourself.
6. Where something a bank would obviously need is simply absent from the evidence, emit a `gap`.
   Do NOT invent the requirement to fill the hole.
"""


class RequirementGatheringAgent(BaseAgent):
    id = "agent1_requirements"
    name = "Requirement Gathering Agent"

    def run(self) -> AgentResult:
        sources = self.ctx.db.scalars(
            select(Source).where(Source.project_id == self.ctx.project_id)
        ).all()
        if not sources:
            raise ValueError("No sources ingested for this project — nothing to gather from.")

        blob = "\n\n".join(
            f"### SOURCE [{s.kind.value}] {s.title}\n"
            f"(id={s.id}, captured={s.created_at:%Y-%m-%d})\n{s.content}"
            for s in sources
        )

        payload = self.generate(
            task="requirement_gathering",
            prompt=PROMPT.format(
                project=self.ctx.project_name,
                sources=blob,
                recall=self.recall(
                    f"prior requirements and standards for {self.ctx.project_name}",
                    namespaces=["org_standard", "reviewer_feedback"],
                ),
                feedback=self.feedback_block(),
            ),
            schema=REQUIREMENTS,
            temperature=0.1,  # extraction, not creativity
        )

        v = self.commit(
            ArtifactType.BUSINESS_REQUIREMENTS,
            payload,
            change_summary="Re-extracted after reviewer feedback" if self.ctx.feedback else "Initial extraction from discovery evidence",
            index_namespace="requirement",
        )

        # Requirements are indexed individually too: downstream agents retrieve at
        # requirement granularity, not document granularity.
        for r in payload.get("requirements", []):
            rag.index(
                project_id=self.ctx.project_id,
                content=f"{r['id']} [{r['priority']}/{r['category']}] {r['title']}\n{r['statement']}",
                namespace="requirement",
                source_id=v.id,
                meta={"requirement_id": r["id"], "priority": r["priority"]},
            )

        n_conf = len(payload.get("conflicts", []))
        n_gap = len(payload.get("gaps", []))
        return AgentResult(
            artifacts={ArtifactType.BUSINESS_REQUIREMENTS.value: v.id},
            payloads={ArtifactType.BUSINESS_REQUIREMENTS.value: payload},
            notes=(
                f"{len(payload.get('requirements', []))} requirements extracted from "
                f"{len(sources)} sources · {n_conf} conflict(s) · {n_gap} gap(s) flagged for human resolution"
            ),
        )
