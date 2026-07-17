"""Process Flow 2 graph — sprint planning, development, testing (PRD §8, §16).

A SEPARATE LangGraph from Flow 1, so extending delivery cannot break requirement generation. It
reuses Flow 1's node wrapper, gate machinery, and approval agent verbatim — the only new shapes are
three delivery gates and the bug rework loop.

Topology:

  agent7 (backlog) → [BTG gate] → agent8 (grooming) → agent9 (dev)
      → [code-review gate] → agent10 (QE)
          ├─ bugs?  → agent9 (rework, bounded, skips re-review) → agent10
          └─ clean  → [completion gate] → agent11 (release) → finalise

The bug decision is the diagram's "bugs identified? → back to development" cycle, modelled as a
first-class, bounded conditional rather than an email chain.
"""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.a5_approval import ApprovalAgent
from app.agents.flow2_agents import (
    BacklogRefinementAgent, DevAssistAgent, GroomingAgent, ReleaseAgent, TestQEAgent,
)
from app.core.db import SessionLocal
from app.core.logging import log
from app.graph import builder as B          # reuse _node, _ctx, _apply_decision, _result_to_state
from app.graph.state import MAX_REVISIONS, SDLCState
from app.models import ArtifactType, Run, RunStatus

BTG_GATE = "btg_gate"
REVIEW_GATE = "review_gate"
COMPLETION_GATE = "completion_gate"
MAX_QE_ROUNDS = 3


# ─────────────────────────────── agent nodes ──────────────────────────────────
@B._node
def agent7_backlog(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = BacklogRefinementAgent(B._ctx(db, state, BTG_GATE)).run()
    return B._result_to_state(db, state, "agent7_backlog", res, time.monotonic() - t0)


@B._node
def agent8_grooming(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = GroomingAgent(B._ctx(db, state)).run()
    return B._result_to_state(db, state, "agent8_grooming", res, time.monotonic() - t0)


@B._node
def agent9_dev(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = DevAssistAgent(B._ctx(db, state, REVIEW_GATE)).run()
    return B._result_to_state(db, state, "agent9_dev", res, time.monotonic() - t0)


@B._node
def agent10_qe(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = TestQEAgent(B._ctx(db, state)).run()
    out = B._result_to_state(db, state, "agent10_qe", res, time.monotonic() - t0)
    # Advance the QE round so a rework loop re-tests as round 2 (clean), bounding the cycle.
    rnd = state.get("revision", {}).get("qe_gate", 0) + 1
    out["revision"] = {"qe_gate": rnd}
    return out


@B._node
def agent11_release(db, state: SDLCState) -> dict[str, Any]:
    t0 = time.monotonic()
    res = ReleaseAgent(B._ctx(db, state)).run()
    return B._result_to_state(db, state, "agent11_release", res, time.monotonic() - t0)


# ─────────────────────────────── gate nodes ───────────────────────────────────
def _request(gate: str, artifact: ArtifactType, prompt: str):
    @B._node
    def node(db, state: SDLCState) -> dict[str, Any]:
        vid = state["artifacts"].get(artifact.value)
        res = ApprovalAgent(
            B._ctx(db, state), gate=gate, artifact_version_id=vid,
            approvers=state["approvers"], base_url=state.get("base_url", "http://localhost:5173"),
        ).run()
        run = db.get(Run, state["run_id"])
        if run:
            run.status = RunStatus.WAITING_APPROVAL
        return B._result_to_state(db, state, node.__name__, res) | {"status": "WAITING_APPROVAL"}
    node.__name__ = f"request_{gate}"
    node.__qualname__ = node.__name__
    return node


def _await(gate: str, artifact: ArtifactType, prompt: str):
    def node(state: SDLCState) -> dict[str, Any]:
        decision = interrupt({
            "gate": gate,
            "artifact_version_id": state["artifacts"].get(artifact.value),
            "approvers": state["approvers"],
            "prompt": prompt,
        })
        return B._apply_decision(state, gate, decision)
    node.__name__ = f"await_{gate}"
    node.__qualname__ = node.__name__
    return node


@B._node
def finalise2(db, state: SDLCState) -> dict[str, Any]:
    from datetime import datetime, timezone

    run = db.get(Run, state["run_id"])
    rejected = any(d == "REJECTED" for d in state.get("gate_decisions", {}).values())
    if run:
        run.status = RunStatus.REJECTED if rejected else RunStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
    B._event(db, state["run_id"], "finalise", "Sprint delivery rejected" if rejected
             else "Sprint delivery completed — handed to DevOps")
    return {"status": "REJECTED" if rejected else "COMPLETED"}


# ─────────────────────────────── routers ──────────────────────────────────────
def _gate_router(gate: str, on_approve: str, on_revise: str):
    def router(state: SDLCState) -> str:
        verdict = state.get("gate_decisions", {}).get(gate, "APPROVED")
        rev = state.get("revision", {}).get(gate, 0)
        if verdict == "APPROVED":
            return on_approve
        if verdict == "REJECTED" or rev >= MAX_REVISIONS:
            log.warning("flow2.gate_exhausted", gate=gate, revisions=rev)
            return "finalise2"
        return on_revise
    return router


def _after_dev(state: SDLCState) -> str:
    """First pass goes through code review; a rework pass (QE already ran) skips straight to QE."""
    return "agent10_qe" if state.get("revision", {}).get("qe_gate", 0) >= 1 else "request_review_gate"


def _after_qe(state: SDLCState) -> str:
    """The diagram's 'bugs identified?' decision — the rework loop, bounded."""
    tc = state.get("payloads", {}).get(ArtifactType.TEST_CASES.value, {})
    rounds = state.get("revision", {}).get("qe_gate", 0)
    if tc.get("bugs_identified") and rounds < MAX_QE_ROUNDS:
        log.info("flow2.rework", round=rounds)
        return "agent9_dev"          # back to development
    return "request_completion_gate"


# ─────────────────────────────── graph ────────────────────────────────────────
def build_flow2_graph(checkpointer):
    g = StateGraph(SDLCState)

    g.add_node("agent7_backlog", agent7_backlog)
    g.add_node("request_btg_gate", _request(BTG_GATE, ArtifactType.REFINED_BACKLOG,
                                            "Refined backlog & estimates awaiting BTG approval"))
    g.add_node("await_btg_gate", _await(BTG_GATE, ArtifactType.REFINED_BACKLOG,
                                        "Refined backlog & estimates awaiting BTG approval"))
    g.add_node("agent8_grooming", agent8_grooming)
    g.add_node("agent9_dev", agent9_dev)
    g.add_node("request_review_gate", _request(REVIEW_GATE, ArtifactType.CODE_REVIEW,
                                               "Code review awaiting Technical-Lead approval"))
    g.add_node("await_review_gate", _await(REVIEW_GATE, ArtifactType.CODE_REVIEW,
                                           "Code review awaiting Technical-Lead approval"))
    g.add_node("agent10_qe", agent10_qe)
    g.add_node("request_completion_gate", _request(COMPLETION_GATE, ArtifactType.TEST_CASES,
                                                   "QE complete — awaiting PO & BTG sign-off"))
    g.add_node("await_completion_gate", _await(COMPLETION_GATE, ArtifactType.TEST_CASES,
                                               "QE complete — awaiting PO & BTG sign-off"))
    g.add_node("agent11_release", agent11_release)
    g.add_node("finalise2", finalise2)

    g.add_edge(START, "agent7_backlog")
    g.add_edge("agent7_backlog", "request_btg_gate")
    g.add_edge("request_btg_gate", "await_btg_gate")
    g.add_conditional_edges("await_btg_gate", _gate_router(BTG_GATE, "agent8_grooming", "agent7_backlog"),
                            ["agent8_grooming", "agent7_backlog", "finalise2"])
    g.add_edge("agent8_grooming", "agent9_dev")
    g.add_conditional_edges("agent9_dev", _after_dev, ["request_review_gate", "agent10_qe"])
    g.add_edge("request_review_gate", "await_review_gate")
    g.add_conditional_edges("await_review_gate", _gate_router(REVIEW_GATE, "agent10_qe", "agent9_dev"),
                            ["agent10_qe", "agent9_dev", "finalise2"])
    g.add_conditional_edges("agent10_qe", _after_qe, ["agent9_dev", "request_completion_gate"])
    g.add_edge("request_completion_gate", "await_completion_gate")
    g.add_conditional_edges("await_completion_gate",
                            _gate_router(COMPLETION_GATE, "agent11_release", "agent9_dev"),
                            ["agent11_release", "agent9_dev", "finalise2"])
    g.add_edge("agent11_release", "finalise2")
    g.add_edge("finalise2", END)

    return g.compile(checkpointer=checkpointer)
