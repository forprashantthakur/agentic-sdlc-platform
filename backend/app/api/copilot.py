"""AI Copilot — grounded chat over the project's own memory.

Not a general chatbot bolted onto the sidebar. Every answer is retrieved from the project's
long-term memory first (sources, requirements, approved artifacts, reviewer feedback), and the
model is instructed to answer ONLY from that context and to say so when the context does not
contain the answer. Citations come back with the answer.

An ungrounded copilot in a requirements tool is worse than no copilot: it invents a requirement,
a BA pastes it into the BRD, and nobody can trace where it came from.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.llm.gemini import gemini
from app.memory import rag
from app.models import ArtifactType, Project
from app.services import versioning

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

SYSTEM = """You are the AI Copilot inside HDFC Bank's Agentic SDLC Platform, assisting a Business
Analyst who is building a Business Requirements Document.

Rules:
1. Answer ONLY from the retrieved project context below. It is the sole source of truth.
2. If the context does not contain the answer, say exactly that, and name what evidence would be
   needed. Do not speculate. A BA will paste your answer into a document a bank builds from.
3. Cite the context blocks you used, by their [n] markers.
4. Be concise and specific. Prefer concrete thresholds, actors and rules over generalities.
"""

PROMPT = """{context}

BUSINESS ANALYST'S QUESTION
{question}

Answer from the context above. Cite the [n] blocks you relied on. If the context does not answer
the question, say so plainly and state what evidence is missing."""


class ChatIn(BaseModel):
    project_id: str
    message: str
    k: int = 6


@router.post("/chat")
def chat(body: ChatIn, db: Session = Depends(get_session)):
    if not db.get(Project, body.project_id):
        raise HTTPException(404, "Project not found")

    hits = rag.retrieve(project_id=body.project_id, query=body.message, k=body.k)
    context = rag.as_context(hits, header="PROJECT CONTEXT") or "(No project memory yet.)"

    answer = gemini().generate_text(
        system=SYSTEM,
        prompt=PROMPT.format(context=context, question=body.message),
        task="copilot",
        temperature=0.2,
    )
    return {
        "answer": answer,
        "citations": [
            {"n": i + 1, "namespace": h["namespace"], "score": round(h["score"], 3),
             "excerpt": h["content"][:220], "meta": h.get("meta") or {}}
            for i, h in enumerate(hits)
        ],
        "grounded": bool(hits),
    }


@router.get("/insights")
def insights(project_id: str, db: Session = Depends(get_session)):
    """What the copilot volunteers without being asked: gaps, conflicts, weak evidence."""
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")

    reqs = versioning.latest(db, project_id, ArtifactType.BUSINESS_REQUIREMENTS)
    if not reqs:
        return {"state": "NO_ANALYSIS", "message": "Run the agents to see extraction insights.",
                "gaps": [], "conflicts": [], "low_confidence": [], "stakeholders": [],
                "mean_confidence": None, "requirement_count": 0}

    p = reqs.payload
    items = p.get("requirements", [])
    confs = [r["confidence"] for r in items if isinstance(r.get("confidence"), (int, float))]
    low = [
        {"id": r["id"], "title": r["title"], "confidence": r["confidence"],
         "open_question": r.get("open_question", "")}
        for r in items
        if isinstance(r.get("confidence"), (int, float)) and r["confidence"] < 0.8
    ]
    return {
        "state": "READY",
        "requirement_count": len(items),
        "mean_confidence": round(sum(confs) / len(confs), 3) if confs else None,
        "gaps": p.get("gaps", []),
        "conflicts": p.get("conflicts", []),
        "low_confidence": low,
        "stakeholders": p.get("stakeholders", []),
    }
