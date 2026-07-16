"""Email intake and inbox-decision paths.

Proves the two enhancements end to end, offline:
  * a requirements email becomes a reviewable draft, then an accepted run;
  * an approver decides from the email — one-click token AND a plain-text reply.
"""

import os
import time

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_intake.db")
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Approval, ApprovalStatus, Base, RunStatus, Source, SourceKind  # noqa: E402

EMAIL = {
    "from": "treasury.head@hdfcbank.com",
    "subject": "New requirement — Corporate FX self-service booking",
    "body": (
        "We need a self-service portal to book FX forwards.\n"
        "Every trade must carry an FEMA purpose code before it can settle.\n"
        "Any deal above USD 10 million should escalate to Market Risk.\n"
        "Live quotes must reach the treasurer within 2 seconds."
    ),
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    # Runs may be suspended at an interrupt (a paused graph schedules no work), so it is safe to
    # reset between tests. We never leave a run *actively executing* at a test boundary — every test
    # that starts one drains it to WAITING_APPROVAL first.
    Base.metadata.drop_all(engine)
    init_db()
    yield


def _pending_tokens(project_id: str) -> list[str]:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(Approval).where(
                Approval.project_id == project_id, Approval.status == ApprovalStatus.PENDING
            )
        ).all()
        return [r.token for r in rows]
    finally:
        db.close()


def test_email_becomes_draft_then_runs(client):
    d = client.post("/api/intake/email", json=EMAIL).json()
    assert d["status"] == "DRAFT"
    assert d["preview"]["candidate_count"] >= 3          # the 'must/should/within' lines
    assert "Corporate FX" in d["name"]

    # a draft is in the intake queue, NOT the normal project list
    assert any(x["id"] == d["id"] for x in client.get("/api/intake").json())
    assert not any(p["id"] == d["id"] for p in client.get("/api/projects").json())

    # the email is stored as evidence
    kinds = [s["kind"] for s in client.get(f"/api/projects/{d['id']}/sources").json()]
    assert SourceKind.EMAIL.value in kinds

    # accept -> pipeline starts, draft leaves the queue and joins the project list
    acc = client.post(f"/api/intake/{d['id']}/accept", json={"approvers": ["cio@hdfcbank.com"]}).json()
    assert acc["status"] == "STARTED" and acc["run_id"]
    assert not any(x["id"] == d["id"] for x in client.get("/api/intake").json())
    assert any(p["id"] == d["id"] for p in client.get("/api/projects").json())
    _drain_to_gate(client, d["id"])   # do not leave a run executing at the test boundary


def test_discard_removes_draft(client):
    d = client.post("/api/intake/email", json=EMAIL).json()
    client.post(f"/api/intake/{d['id']}/discard")
    assert client.get("/api/intake").json() == []


def test_empty_body_rejected(client):
    r = client.post("/api/intake/email", json={"from": "a@b.com", "subject": "x", "body": "   "})
    assert r.status_code == 400


def _drain_terminal(client, project_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        runs = client.get(f"/api/runs?project_id={project_id}").json()
        if runs and runs[0]["status"] in (RunStatus.COMPLETED.value, RunStatus.FAILED.value,
                                          RunStatus.REJECTED.value):
            return runs[0]["status"]
        time.sleep(0.05)
    pytest.fail("run did not reach a terminal state")


def _drain_to_gate(client, project_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        runs = client.get(f"/api/runs?project_id={project_id}").json()
        if runs and runs[0]["status"] in (RunStatus.WAITING_APPROVAL.value,
                                          RunStatus.COMPLETED.value, RunStatus.FAILED.value):
            return
        time.sleep(0.05)


def _reach_gate(client, approvers):
    d = client.post("/api/intake/email", json=EMAIL).json()
    client.post(f"/api/intake/{d['id']}/accept", json={"approvers": approvers})
    deadline = time.time() + 60
    while time.time() < deadline:
        runs = client.get(f"/api/runs?project_id={d['id']}").json()
        if runs and runs[0]["status"] == RunStatus.WAITING_APPROVAL.value:
            return d["id"]
        time.sleep(0.05)
    pytest.fail("gate not reached")


def test_one_click_token_decision(client):
    pid = _reach_gate(client, ["approver@hdfcbank.com"])
    tok = _pending_tokens(pid)[0]
    r = client.post(f"/api/approvals/by-token/{tok}/decide",
                    json={"decision": "APPROVED", "comments": []}).json()
    assert r["status"] == "RESUMED" and r["verdict"] == "APPROVED"
    _drain_to_gate(client, pid)   # the resume advances to the next gate; let it settle


def test_tampered_token_is_rejected(client):
    _reach_gate(client, ["approver@hdfcbank.com"])
    r = client.post("/api/approvals/by-token/nonsense.token/decide",
                    json={"decision": "APPROVED", "comments": []})
    assert r.status_code == 401


def test_email_reply_is_parsed(client):
    pid = _reach_gate(client, ["approver@hdfcbank.com"])
    r = client.post("/api/approvals/reply",
                    json={"from": "APPROVER@hdfcbank.com", "body": "APPROVED — ship it"}).json()
    assert r["status"] == "RESUMED" and r["verdict"] == "APPROVED"
    _drain_to_gate(client, pid)


def test_unreadable_reply_rejected(client):
    _reach_gate(client, ["approver@hdfcbank.com"])
    r = client.post("/api/approvals/reply", json={"from": "approver@hdfcbank.com", "body": "thanks!"})
    assert r.status_code == 422


def test_quorum_requires_all_approvers(client):
    pid = _reach_gate(client, ["a@hdfcbank.com", "b@hdfcbank.com"])
    t = _pending_tokens(pid)
    first = client.post(f"/api/approvals/by-token/{t[0]}/decide",
                        json={"decision": "APPROVED", "comments": []}).json()
    assert first["status"] == "WAITING_FOR_OTHER_APPROVERS"
    second = client.post("/api/approvals/reply",
                         json={"from": "b@hdfcbank.com", "body": "APPROVED"}).json()
    assert second["status"] == "RESUMED"
    _drain_to_gate(client, pid)
