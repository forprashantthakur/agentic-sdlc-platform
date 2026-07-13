"""The multi-agent graph.

    ingest → A1 requirements ─┐
                              ├→ A2 concept note → [A5 gate: concept] ──approved──┐
                              └──────────────changes requested────────────────────┘ (loops back to A2
                                                                                     carrying comments)
    → A3 wireframes → A4 requirement docs → [A5 gate: requirement docs] ──approved──→ A6 sprint → done
                            ↑                                            changes requested
                            └────────────────────────────────────────────────────────┘

Two structural choices worth calling out:

1. Each gate is TWO nodes — `request_*` (sends the email, writes the Approval rows) and
   `await_*` (calls `interrupt()`). LangGraph re-runs a node from the top when a run resumes,
   so putting the side effect in the same node as the interrupt would email the approver again
   on every resume. Splitting them makes the gate idempotent.

2. The interrupt is a real suspension, not a poll. The run's state is checkpointed to Postgres,
   the process can be redeployed, and the run resumes on `Command(resume=...)` days later —
   which is exactly the latency of a real bank approval.
"""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.a1_requirement_gathering import RequirementGatheringAgent
from app.agents.a2_concept_note import ConceptNoteAgent
from app.agents.a3_wireframe import WireframeAgent
from app.agents.a4_requirement_docs import RequirementDocumentAgent
from app.agents.a5_approval import ApprovalAgent
from app.agents.a6_sprint import SprintAgent
from app.agents.base import AgentContext
from app.core import progress
from app.core.db import SessionLocal
from app.core.logging import log
from app.graph.state import MAX_REVISIONS, SDLCState
from app.memory import rag
from app.models import ArtifactType, Run, RunEvent, RunStatus, Source
from app.services import versioning

CONCEPT_GATE = "concept_note_gate"
DOCS_GATE = "requirement_docs_gate"


# ────────────────────────────── infrastructure ────────────────────────────────
def _event(db, run_id: str, node: str, message: str, data: dict | None = None, level: str = "info"):
    db.add(RunEvent(run_id=run_id, node=node, level=level, message=message, data=data or {}))
    run = db.get(Run, run_id)
    if run:
        run.current_node = node
    db.flush()


def _ctx(db, state: SDLCState, gate: str | None = None) -> AgentContext:
    fb = state.get("feedback", {}).get(gate, []) if gate else []
    return AgentContext(
        db=db,
        project_id=state["project_id"],
        project_name=state["project_name"],
        run_id=state["run_id"],
        state={"payloads": state.get("payloads", {}), "artifacts": state.get("artifacts", {})},
        feedback=fb,
    )


def _node(fn):
    """Every agent node gets a session, an audit event, uniform error capture, a progress channel
    and a stopwatch.

    The channel matters more than it sounds: without it, a model backing off for thirty seconds is
    indistinguishable from a hang. The stopwatch matters because "why is this slow" is unanswerable
    without it — now every agent reports how long it actually took.
    """

    def wrapper(state: SDLCState) -> dict[str, Any]:
        name = fn.__name__
        db = SessionLocal()
        started = time.monotonic()

        def report(message: str, level: str = "info") -> None:
            # A separate session: the node's own transaction may be mid-flight, and a progress note
            # must never be rolled back with it.
            s = SessionLocal()
            try:
                s.add(RunEvent(run_id=state["run_id"], node=name, level=level, message=message))
                s.commit()
            finally:
                s.close()

        token = progress.set_channel(report)
        try:
            _event(db, state["run_id"], name, f"{name} started")
            db.commit()

            out = fn(db, state)

            db.commit()
            return out
        except Exception as e:
            db.rollback()
            log.exception("node.failed", node=name)
            _event(db, state["run_id"], name, f"{name} FAILED: {e}", level="error")
            run = db.get(Run, state["run_id"])
            if run:
                run.status = RunStatus.FAILED
                run.error = str(e)
            db.commit()
            raise
        finally:
            progress.reset_channel(token)
            db.close()

    wrapper.__name__ = fn.__name__
    return wrapper


def _result_to_state(db, state: SDLCState, node: str, res, seconds: float | None = None) -> dict[str, Any]:
    note = res.notes if seconds is None else f"{res.notes}  ·  {seconds:.0f}s"
    _event(db, state["run_id"], node, note,
           {"artifacts": res.artifacts, "external": res.external, "seconds": seconds})
    return {
        "payloads": res.payloads,
        "artifacts": res.artifacts,
        "external": res.external,
        "trace": [{"node": node, "notes": res.notes}],
        "status": "RUNNING",
    }


# ─────────────────────────────────── nodes ────────────────────────────────────
@_node
def ingest(db, state: SDLCState) -> dict[str, Any]:
    """Index every raw source into long-term memory. Idempotent per run."""
    sources = db.query(Source).filter(Source.project_id == state["project_id"]).all()
    rag.get_vector_store = rag.get_vector_store  # noqa: B018 (keeps the import obvious)
    total = 0
    for s in sources:
        total += rag.index(
            project_id=state["project_id"],
            content=f"[{s.kind.value}] {s.title}\n\n{s.content}",
            namespace="source",
            source_id=s.id,
            meta={"kind": s.kind.value, "title": s.title},
        )
    _event(db, state["run_id"], "ingest", f"Indexed {len(sources)} sources into {total} memory chunks")
    run = db.get(Run, state["run_id"])
    if run:
        run.status = RunStatus.RUNNING
    return {"status": "RUNNING", "trace": [{"node": "ingest", "notes": f"{total} chunks indexed"}]}


@_node
def agent1_requirements(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = RequirementGatheringAgent(_ctx(db, state)).run()
    return _result_to_state(db, state, "agent1_requirements", res, time.monotonic() - t0)


@_node
def agent2_concept_note(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = ConceptNoteAgent(_ctx(db, state, CONCEPT_GATE)).run()
    return _result_to_state(db, state, "agent2_concept_note", res, time.monotonic() - t0)


@_node
def request_concept_approval(db, state: SDLCState) -> dict[str, Any]:
    vid = state["artifacts"][ArtifactType.CONCEPT_NOTE.value]
    res = ApprovalAgent(
        _ctx(db, state), gate=CONCEPT_GATE, artifact_version_id=vid,
        approvers=state["approvers"], base_url=state.get("base_url", "http://localhost:5173"),
    ).run()
    run = db.get(Run, state["run_id"])
    if run:
        run.status = RunStatus.WAITING_APPROVAL
    return _result_to_state(db, state, "request_concept_approval", res) | {"status": "WAITING_APPROVAL"}


def await_concept_approval(state: SDLCState) -> dict[str, Any]:
    """Suspends the run. Resumed by POST /api/approvals/{id}/decide → Command(resume=...)."""
    decision: dict[str, Any] = interrupt(
        {
            "gate": CONCEPT_GATE,
            "artifact_version_id": state["artifacts"][ArtifactType.CONCEPT_NOTE.value],
            "approvers": state["approvers"],
            "prompt": "Concept Note awaiting sign-off",
        }
    )
    return _apply_decision(state, CONCEPT_GATE, decision)


@_node
def agent3_wireframe(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = WireframeAgent(_ctx(db, state, DOCS_GATE)).run()
    return _result_to_state(db, state, "agent3_wireframe", res, time.monotonic() - t0)


@_node
def agent4_requirement_docs(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = RequirementDocumentAgent(_ctx(db, state, DOCS_GATE)).run()
    return _result_to_state(db, state, "agent4_requirement_docs", res, time.monotonic() - t0)


@_node
def request_docs_approval(db, state: SDLCState) -> dict[str, Any]:
    vid = state["artifacts"][ArtifactType.BRD.value]
    res = ApprovalAgent(
        _ctx(db, state), gate=DOCS_GATE, artifact_version_id=vid,
        approvers=state["approvers"], base_url=state.get("base_url", "http://localhost:5173"),
    ).run()
    run = db.get(Run, state["run_id"])
    if run:
        run.status = RunStatus.WAITING_APPROVAL
    return _result_to_state(db, state, "request_docs_approval", res) | {"status": "WAITING_APPROVAL"}


def await_docs_approval(state: SDLCState) -> dict[str, Any]:
    decision: dict[str, Any] = interrupt(
        {
            "gate": DOCS_GATE,
            "artifact_version_id": state["artifacts"][ArtifactType.BRD.value],
            "approvers": state["approvers"],
            "prompt": "Requirement documentation set awaiting sign-off",
        }
    )
    return _apply_decision(state, DOCS_GATE, decision)


@_node
def agent6_sprint(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = SprintAgent(_ctx(db, state), velocity=state.get("velocity", 15)).run()
    return _result_to_state(db, state, "agent6_sprint", res, time.monotonic() - t0)


@_node
def finalise(db, state: SDLCState) -> dict[str, Any]:
    run = db.get(Run, state["run_id"])
    rejected = any(d == "REJECTED" for d in state.get("gate_decisions", {}).values())
    if run:
        from datetime import datetime, timezone

        run.status = RunStatus.REJECTED if rejected else RunStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
    _event(db, state["run_id"], "finalise", "Run rejected" if rejected else "Run completed")
    return {"status": "REJECTED" if rejected else "COMPLETED"}


# ────────────────────────── gate decision handling ────────────────────────────
def _apply_decision(state: SDLCState, gate: str, decision: dict[str, Any]) -> dict[str, Any]:
    verdict = (decision or {}).get("decision", "APPROVED")
    comments: list[str] = (decision or {}).get("comments", [])
    rev = state.get("revision", {}).get(gate, 0)

    db = SessionLocal()
    try:
        _event(db, state["run_id"], f"await_{gate}", f"Gate decision: {verdict}",
               {"comments": comments, "revision": rev})

        if verdict == "APPROVED":
            # Approve the exact version that was reviewed — not "the latest".
            for atype in _gate_artifacts(gate):
                vid = state["artifacts"].get(atype.value)
                if vid:
                    from app.models import ArtifactVersion

                    v = db.get(ArtifactVersion, vid)
                    if v:
                        versioning.approve(db, v)
        elif comments:
            # Rejected feedback becomes long-term memory: the next generation retrieves it,
            # and so does every future project in this business unit.
            for c in comments:
                rag.index(
                    project_id=state["project_id"],
                    content=f"Reviewer feedback at {gate} (round {rev + 1}): {c}",
                    namespace="reviewer_feedback",
                    meta={"gate": gate, "round": rev + 1},
                )
        db.commit()
    finally:
        db.close()

    return {
        "gate_decisions": {gate: verdict},
        "feedback": {gate: comments},
        "revision": {gate: rev + 1},
        "trace": [{"node": f"await_{gate}", "notes": f"{verdict} ({len(comments)} comments)"}],
        "status": "RUNNING" if verdict == "APPROVED" else "REVISING",
    }


def _gate_artifacts(gate: str) -> list[ArtifactType]:
    if gate == CONCEPT_GATE:
        return [ArtifactType.CONCEPT_NOTE, ArtifactType.BUSINESS_REQUIREMENTS]
    return [
        ArtifactType.BRD, ArtifactType.FRD, ArtifactType.SRS, ArtifactType.WIREFRAME,
        ArtifactType.USER_STORIES, ArtifactType.ACCEPTANCE_CRITERIA,
        ArtifactType.API_REQUIREMENTS, ArtifactType.NFR,
    ]


def _route(gate: str, on_approve: str, on_revise: str):
    def router(state: SDLCState) -> str:
        verdict = state.get("gate_decisions", {}).get(gate, "APPROVED")
        rev = state.get("revision", {}).get(gate, 0)
        if verdict == "APPROVED":
            return on_approve
        if verdict == "REJECTED" or rev >= MAX_REVISIONS:
            # A gate that has looped MAX_REVISIONS times is not an AI problem — escalate to humans.
            log.warning("gate.exhausted", gate=gate, revisions=rev)
            return "finalise"
        return on_revise

    return router


# ────────────────────────────────── assembly ──────────────────────────────────
def build_graph(checkpointer):
    g = StateGraph(SDLCState)

    g.add_node("ingest", ingest)
    g.add_node("agent1_requirements", agent1_requirements)
    g.add_node("agent2_concept_note", agent2_concept_note)
    g.add_node("request_concept_approval", request_concept_approval)
    g.add_node("await_concept_approval", await_concept_approval)
    g.add_node("agent3_wireframe", agent3_wireframe)
    g.add_node("agent4_requirement_docs", agent4_requirement_docs)
    g.add_node("request_docs_approval", request_docs_approval)
    g.add_node("await_docs_approval", await_docs_approval)
    g.add_node("agent6_sprint", agent6_sprint)
    g.add_node("finalise", finalise)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "agent1_requirements")
    g.add_edge("agent1_requirements", "agent2_concept_note")
    g.add_edge("agent2_concept_note", "request_concept_approval")
    g.add_edge("request_concept_approval", "await_concept_approval")

    g.add_conditional_edges(
        "await_concept_approval",
        _route(CONCEPT_GATE, on_approve="agent3_wireframe", on_revise="agent2_concept_note"),
        ["agent3_wireframe", "agent2_concept_note", "finalise"],
    )

    g.add_edge("agent3_wireframe", "agent4_requirement_docs")
    g.add_edge("agent4_requirement_docs", "request_docs_approval")
    g.add_edge("request_docs_approval", "await_docs_approval")

    g.add_conditional_edges(
        "await_docs_approval",
        _route(DOCS_GATE, on_approve="agent6_sprint", on_revise="agent4_requirement_docs"),
        ["agent6_sprint", "agent4_requirement_docs", "finalise"],
    )

    g.add_edge("agent6_sprint", "finalise")
    g.add_edge("finalise", END)

    return g.compile(checkpointer=checkpointer)
