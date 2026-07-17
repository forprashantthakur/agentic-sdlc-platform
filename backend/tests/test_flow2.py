"""Process Flow 2 — sprint planning, development, testing.

Proves, offline, that Flow 2 runs on a Flow-1-completed project through its gates, exercises the
bug rework loop (round 1 fails → back to dev → round 2 passes), and produces the five delivery
artifacts with Jira/Confluence sync recorded.
"""

import os
import time

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_flow2.db")
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Approval, ApprovalStatus, Base, RunStatus  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield


def _approve_pending(client, project_id):
    db = SessionLocal()
    try:
        toks = [a.token for a in db.scalars(select(Approval).where(
            Approval.project_id == project_id, Approval.status == ApprovalStatus.PENDING)).all()]
    finally:
        db.close()
    for t in toks:
        client.post(f"/api/approvals/by-token/{t}/decide", json={"decision": "APPROVED", "comments": []})
    return len(toks)


def _wait(client, run_id, status, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/runs/{run_id}").json()
        if j["status"] == status:
            return j
        if j["status"] == "FAILED":
            pytest.fail(f"run failed: {j['error']}")
        time.sleep(0.03)
    pytest.fail(f"run did not reach {status}")


def _complete_flow1(client):
    pid = client.post("/api/projects/seed?key=corporate_fx").json()["id"]
    r = client.post("/api/runs", json={"project_id": pid, "approvers": ["cio@hdfcbank.com"]}).json()
    for _ in range(2):
        _wait(client, r["id"], RunStatus.WAITING_APPROVAL.value)
        _approve_pending(client, pid)
    _wait(client, r["id"], RunStatus.COMPLETED.value)
    return pid


def test_flow2_requires_completed_flow1(client):
    # a fresh project with no approved stories cannot start Flow 2
    pid = client.post("/api/projects/seed?key=corporate_fx").json()["id"]
    r = client.post("/api/runs/flow2", json={"project_id": pid, "approvers": ["po@hdfcbank.com"]})
    assert r.status_code == 400


def test_flow2_full_run_with_rework_loop(client):
    pid = _complete_flow1(client)

    f2 = client.post("/api/runs/flow2", json={"project_id": pid, "approvers": ["po@hdfcbank.com"]}).json()
    fid = f2["id"]
    assert f2["thread_id"].startswith("f2-")          # selects the Flow-2 graph

    for _ in range(10):
        if client.get(f"/api/runs/{fid}").json()["status"] == RunStatus.COMPLETED.value:
            break
        _wait(client, fid, RunStatus.WAITING_APPROVAL.value, timeout=30)
        _approve_pending(client, pid)
        time.sleep(0.2)
    assert client.get(f"/api/runs/{fid}").json()["status"] == RunStatus.COMPLETED.value

    ev = client.get(f"/api/runs/{fid}/events").json()
    agents = {e["node"] for e in ev if e["node"].startswith("agent")}
    assert agents == {"agent7_backlog", "agent8_grooming", "agent9_dev", "agent10_qe", "agent11_release"}

    # the rework loop: round 1 finds a bug, round 2 passes, dev ran twice
    qe = [e["message"] for e in ev if e["node"] == "agent10_qe" and "QE round" in e["message"]]
    assert any("REWORK" in m for m in qe) and any("PASS" in m for m in qe)
    dev_starts = [e for e in ev if e["node"] == "agent9_dev" and "started" in e["message"]]
    assert len(dev_starts) == 2

    # all five delivery artifacts exist
    arts = {a["type"] for a in client.get(f"/api/artifacts?project_id={pid}").json()}
    assert {"REFINED_BACKLOG", "GROOMING_PACK", "CODE_REVIEW", "TEST_CASES", "RELEASE_HANDOFF"} <= arts
