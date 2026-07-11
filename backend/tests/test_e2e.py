"""End-to-end: six agents, two approval gates, a revision loop, and full versioning.

Runs entirely offline (MOCK_MODE + SQLite + in-memory vector store). This is the test that
proves the graph topology, the interrupt/resume mechanics and the versioning rules —
not the model's prose.
"""

import os

os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sdlc.db")
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402

from app.core.db import SessionLocal, engine, init_db  # noqa: E402
from app.models import (  # noqa: E402
    Approval, ApprovalStatus, Artifact, ArtifactType, ArtifactVersion, Base,
    Project, Run, RunStatus, Source,
)
from app.seed import SEED_SOURCES  # noqa: E402
from app.services import runner, versioning  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield


def _project() -> str:
    db = SessionLocal()
    try:
        p = Project(name="UPI AutoPay Self-Service", business_unit="Retail Banking")
        db.add(p)
        db.flush()
        for s in SEED_SOURCES:
            db.add(Source(project_id=p.id, kind=s["kind"], title=s["title"], content=s["content"]))
        db.commit()
        return p.id
    finally:
        db.close()


def _wait(run_id: str, status: RunStatus, timeout: float = 90.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        db = SessionLocal()
        try:
            r = db.get(Run, run_id)
            if r.status == status:
                return r
            if r.status == RunStatus.FAILED:
                pytest.fail(f"Run failed: {r.error}")
        finally:
            db.close()
        time.sleep(0.25)
    pytest.fail(f"Timed out waiting for {status}; run never got there.")


def _pending(run_id: str, gate: str) -> Approval:
    db = SessionLocal()
    try:
        return (
            db.query(Approval)
            .filter(Approval.run_id == run_id, Approval.gate == gate,
                    Approval.status == ApprovalStatus.PENDING)
            .first()
        )
    finally:
        db.close()


def _decide(approval_id: str, decision: ApprovalStatus, comments: list[str]):
    from app.api.approvals import decide
    from app.schemas import CommentIn, DecisionIn

    db = SessionLocal()
    try:
        return decide(
            approval_id,
            DecisionIn(
                decision=decision,
                comments=[CommentIn(author="compliance@hdfcbank.com", body=c) for c in comments],
            ),
            db,
        )
    finally:
        db.close()


def test_full_workflow_with_a_revision_loop():
    pid = _project()
    run = runner.start_run(project_id=pid, approvers=["compliance@hdfcbank.com"], velocity=15)

    # ── Gate 1: the concept note comes back for changes ───────────────────────
    _wait(run.id, RunStatus.WAITING_APPROVAL)
    a1 = _pending(run.id, "concept_note_gate")
    assert a1 is not None, "Agent 5 did not raise an approval at the concept-note gate"

    _decide(a1.id, ApprovalStatus.CHANGES_REQUESTED,
            ["Retry cap conflict is unresolved — state it explicitly as a risk.",
             "Add the frozen/dormant account rule to the business rules."])

    # Agent 2 re-runs with the feedback, and Agent 5 raises a *new* approval round.
    _wait(run.id, RunStatus.WAITING_APPROVAL)
    a1b = _pending(run.id, "concept_note_gate")
    assert a1b is not None and a1b.id != a1.id, "Revision loop did not open a fresh approval round"

    _decide(a1b.id, ApprovalStatus.APPROVED, [])

    # ── Gate 2: the documentation set is approved first time ──────────────────
    _wait(run.id, RunStatus.WAITING_APPROVAL)
    a2 = _pending(run.id, "requirement_docs_gate")
    assert a2 is not None, "Agent 5 did not raise an approval at the documentation gate"
    _decide(a2.id, ApprovalStatus.APPROVED, [])

    _wait(run.id, RunStatus.COMPLETED)

    # ── Assertions on what the six agents actually produced ───────────────────
    db = SessionLocal()
    try:
        types = {a.type for a in db.query(Artifact).filter(Artifact.project_id == pid)}
        expected = {
            ArtifactType.BUSINESS_REQUIREMENTS, ArtifactType.CONCEPT_NOTE, ArtifactType.WIREFRAME,
            ArtifactType.BRD, ArtifactType.FRD, ArtifactType.SRS, ArtifactType.USER_STORIES,
            ArtifactType.ACCEPTANCE_CRITERIA, ArtifactType.API_REQUIREMENTS, ArtifactType.NFR,
            ArtifactType.SPRINT_PLAN,
        }
        assert expected <= types, f"Missing artifacts: {expected - types}"

        # The revision loop must have produced a genuinely new version, not a rewrite of v1.
        cn = versioning.latest(db, pid, ArtifactType.CONCEPT_NOTE)
        assert cn.version == 2, "Reviewer feedback did not produce a v2 of the concept note"
        assert cn.change_summary == "Revised per reviewer comments"

        # Approved-version semantics: the reviewed version is the approved one, and v1 is not.
        approved = versioning.latest_approved(db, pid, ArtifactType.CONCEPT_NOTE)
        assert approved is not None and approved.version == 2
        v1 = next(v for v in cn.artifact.versions if v.version == 1)
        assert not v1.approved, "Superseded v1 must not be marked approved"

        # Every artifact carries a full, attributed version lineage.
        for v in db.query(ArtifactVersion):
            assert v.produced_by.startswith("agent")
            assert v.content_hash
            assert v.rendered_md

        # Jira tickets were written from the sprint plan.
        sp = versioning.latest(db, pid, ArtifactType.SPRINT_PLAN)
        assert sp.payload["jira"], "Sprint agent produced no Jira issues"
        assert any(i["type"] == "Epic" for i in sp.payload["jira"])

        # Approval emails went out — one per round, per approver.
        from app.adapters.gmail import MockGmailAdapter

        assert len(MockGmailAdapter.outbox) >= 3, "Expected 3 approval emails (2 concept rounds + 1 docs)"

        run_row = db.get(Run, run.id)
        assert run_row.status == RunStatus.COMPLETED
    finally:
        db.close()


def test_versioning_is_content_addressed():
    """An identical regeneration must not create a new version — replays stay idempotent."""
    pid = _project()
    db = SessionLocal()
    try:
        payload = {"title": "t", "sections": [{"heading": "h", "body": "b"}], "traceability": []}
        v1 = versioning.commit_version(
            db=db, project_id=pid, atype=ArtifactType.BRD, payload=payload,
            rendered_md="# t", produced_by="agent4", run_id=None, model="mock",
        )
        v2 = versioning.commit_version(
            db=db, project_id=pid, atype=ArtifactType.BRD, payload=payload,
            rendered_md="# t", produced_by="agent4", run_id=None, model="mock",
        )
        assert v1.id == v2.id and v1.version == 1

        v3 = versioning.commit_version(
            db=db, project_id=pid, atype=ArtifactType.BRD, payload={**payload, "title": "t2"},
            rendered_md="# t2", produced_by="agent4", run_id=None, model="mock",
        )
        assert v3.version == 2
        assert "t2" in versioning.diff(v1, v3)
        db.commit()
    finally:
        db.close()


def test_rag_retrieval_is_namespaced():
    pid = _project()
    from app.memory import rag

    rag.index(project_id=pid, content="RBI e-mandate: AFA required above INR 1,00,000.",
              namespace="org_standard")
    rag.index(project_id=pid, content="Reviewer: tighten the retry cap rule.",
              namespace="reviewer_feedback")

    hits = rag.retrieve(project_id=pid, query="AFA threshold", k=5, namespaces=["org_standard"])
    assert hits and all(h["namespace"] == "org_standard" for h in hits)
