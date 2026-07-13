"""Run lifecycle: start, suspend at a gate, resume, replay.

A "run" is one pass of the graph for one project. It is identified by a `thread_id`, which
is the LangGraph checkpoint key. Everything about resumability hangs off that id: the run
can be interrupted at an approval gate, the backend can be redeployed, and a resume days
later picks up from the exact checkpoint.

Graph execution happens on a worker thread so the HTTP request that starts a run returns
immediately; the UI follows progress over SSE from the run_events table.
"""

from __future__ import annotations

import threading
from typing import Any

from langgraph.types import Command

from app.core.db import SessionLocal
from app.core.logging import log
from app.graph.builder import build_graph
from app.memory import shared
from app.memory.short_term import checkpointer
from app.models import Project, Run, RunStatus

_lock = threading.Lock()
_active: dict[str, threading.Thread] = {}


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}


def _execute(thread_id: str, payload: Any) -> None:
    """Drive the graph until it either finishes or hits an interrupt."""
    try:
        with checkpointer() as cp:
            graph = build_graph(cp)
            # One retrieval scope for the WHOLE run, opened here rather than inside a node.
            # LangGraph copies the context into each parallel worker thread, so a scope opened in a
            # node is private to that node — the memo would never be hit by the branch beside it.
            rag_token = shared.begin_run()
            try:
                for chunk in graph.stream(payload, _config(thread_id), stream_mode="updates"):
                    if "__interrupt__" in chunk:
                        log.info("run.suspended", thread=thread_id)
                        return
            finally:
                shared.end_run(rag_token)
        log.info("run.finished", thread=thread_id)
    except Exception as e:
        log.exception("run.failed", thread=thread_id)
        db = SessionLocal()
        try:
            run = db.query(Run).filter(Run.thread_id == thread_id).first()
            if run and run.status not in (RunStatus.COMPLETED, RunStatus.REJECTED):
                run.status = RunStatus.FAILED
                run.error = str(e)
                db.commit()
        finally:
            db.close()
    finally:
        with _lock:
            _active.pop(thread_id, None)


def _spawn(thread_id: str, payload: Any) -> None:
    with _lock:
        if thread_id in _active:
            raise RuntimeError("This run is already executing.")
        t = threading.Thread(target=_execute, args=(thread_id, payload), daemon=True)
        _active[thread_id] = t
    t.start()


def start_run(
    *, project_id: str, approvers: list[str], velocity: int = 15,
    base_url: str = "http://localhost:5173",
) -> Run:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError("Unknown project")

        run = Run(project_id=project_id, thread_id="", status=RunStatus.PENDING)
        db.add(run)
        db.flush()
        run.thread_id = f"run-{run.id}"
        db.commit()

        payload = {
            "project_id": project_id,
            "project_name": project.name,
            "run_id": run.id,
            "approvers": approvers,
            "velocity": velocity,
            "base_url": base_url,
            "payloads": {},
            "artifacts": {},
            "external": {},
            "gate_decisions": {},
            "feedback": {},
            "revision": {},
            "trace": [],
            "status": "RUNNING",
        }
        thread_id = run.thread_id
        run_id = run.id
    finally:
        db.close()

    _spawn(thread_id, payload)

    db = SessionLocal()
    try:
        return db.get(Run, run_id)
    finally:
        db.close()


def resume_run(*, run: Run, decision: str, comments: list[str]) -> None:
    """Feed a human decision back into the suspended graph."""
    _spawn(run.thread_id, Command(resume={"decision": decision, "comments": comments}))


def get_state(thread_id: str) -> dict[str, Any]:
    with checkpointer() as cp:
        graph = build_graph(cp)
        snap = graph.get_state(_config(thread_id))
    return {
        "values": snap.values,
        "next": list(snap.next),
        "interrupts": [
            {"value": i.value, "id": getattr(i, "id", None)} for i in (snap.tasks[0].interrupts if snap.tasks else [])
        ] if snap.tasks else [],
    }


def history(thread_id: str, limit: int = 25) -> list[dict[str, Any]]:
    """Checkpoint history — this is the time-machine that makes a run replayable for audit."""
    with checkpointer() as cp:
        graph = build_graph(cp)
        out = []
        for snap in graph.get_state_history(_config(thread_id)):
            out.append({
                "checkpoint_id": snap.config["configurable"].get("checkpoint_id"),
                "next": list(snap.next),
                "status": snap.values.get("status"),
                "created_at": snap.created_at,
            })
            if len(out) >= limit:
                break
    return out
