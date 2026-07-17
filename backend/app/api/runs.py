from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_session
from app.models import Run, RunEvent
from pydantic import BaseModel
from app.schemas import EventOut, RunIn, RunOut
from app.services import runner

router = APIRouter(prefix="/api/runs", tags=["runs"])


class Flow2In(BaseModel):
    project_id: str
    approvers: list[str] = []
    base_url: str = "http://localhost:5173"


@router.post("/flow2", response_model=RunOut, status_code=202)
def start_flow2(body: Flow2In):
    """Start Process Flow 2 (sprint planning, development, testing) on a Flow-1-completed project."""
    try:
        run = runner.start_flow2(
            project_id=body.project_id,
            approvers=[str(a) for a in body.approvers],
            base_url=body.base_url,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return run


@router.post("", response_model=RunOut, status_code=202)
def start(body: RunIn):
    try:
        run = runner.start_run(
            project_id=body.project_id,
            approvers=[str(a) for a in body.approvers],
            velocity=body.velocity,
            base_url=body.base_url,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return run


@router.get("", response_model=list[RunOut])
def list_runs(project_id: str | None = None, db: Session = Depends(get_session)):
    q = select(Run).order_by(Run.started_at.desc())
    if project_id:
        q = q.where(Run.project_id == project_id)
    return list(db.scalars(q))


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_session)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/events", response_model=list[EventOut])
def events(run_id: str, after: int = 0, db: Session = Depends(get_session)):
    return list(
        db.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > after)
            .order_by(RunEvent.id)
        )
    )


@router.get("/{run_id}/state")
def graph_state(run_id: str, db: Session = Depends(get_session)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return runner.get_state(run.thread_id)


@router.get("/{run_id}/history")
def checkpoint_history(run_id: str, db: Session = Depends(get_session)):
    """Checkpoint-by-checkpoint replay of the run — the audit view."""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return runner.history(run.thread_id)


@router.get("/{run_id}/stream")
async def stream(run_id: str):
    """SSE feed of run events — what the console's live timeline consumes."""

    async def gen():
        last = 0
        idle = 0
        while idle < 600:  # ~10 minutes of silence before we hang up
            db = SessionLocal()
            try:
                rows = db.scalars(
                    select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > last)
                    .order_by(RunEvent.id)
                ).all()
                run = db.get(Run, run_id)
                status = run.status.value if run else "UNKNOWN"
            finally:
                db.close()

            if rows:
                idle = 0
                for e in rows:
                    last = e.id
                    payload = {
                        "id": e.id, "node": e.node, "level": e.level, "message": e.message,
                        "data": e.data, "status": status,
                        "created_at": e.created_at.isoformat(),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
            else:
                idle += 1
                yield ": keep-alive\n\n"

            if status in ("COMPLETED", "FAILED", "REJECTED", "WAITING_APPROVAL") and not rows:
                yield f"data: {json.dumps({'terminal': True, 'status': status})}\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
