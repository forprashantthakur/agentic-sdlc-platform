"""Dialect-neutral ORM models.

Vector storage lives in `app.memory.vector_store` (raw SQL against pgvector, or an
in-process fallback) so the relational schema stays portable.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ─────────────────────────────── enums ────────────────────────────────────────
class ArtifactType(str, enum.Enum):
    BUSINESS_REQUIREMENTS = "BUSINESS_REQUIREMENTS"   # Agent 1
    CONCEPT_NOTE = "CONCEPT_NOTE"                     # Agent 2
    WIREFRAME = "WIREFRAME"                           # Agent 3
    BRD = "BRD"                                       # Agent 4
    FRD = "FRD"
    SRS = "SRS"
    USER_STORIES = "USER_STORIES"
    API_REQUIREMENTS = "API_REQUIREMENTS"
    NFR = "NFR"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    SPRINT_PLAN = "SPRINT_PLAN"                       # Agent 6
    # ── Process Flow 2 — sprint planning, development, testing ──
    REFINED_BACKLOG = "REFINED_BACKLOG"               # Agent 7
    GROOMING_PACK = "GROOMING_PACK"                   # Agent 8
    CODE_REVIEW = "CODE_REVIEW"                       # Agent 9
    TEST_CASES = "TEST_CASES"                         # Agent 10
    RELEASE_HANDOFF = "RELEASE_HANDOFF"               # Agent 11


class RunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class SourceKind(str, enum.Enum):
    MEETING_NOTES = "MEETING_NOTES"
    EMAIL = "EMAIL"
    VOICE_TRANSCRIPT = "VOICE_TRANSCRIPT"
    DOCUMENT = "DOCUMENT"


# ─────────────────────────────── tables ───────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    business_unit: Mapped[str] = mapped_column(String(120), default="Retail Banking")
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(200), default="system")
    # Structured business context captured at intake: sponsor, owner, priority, objectives,
    # problem statement, KPIs, business value, timeline, budget. JSON rather than 15 columns
    # because it is a form payload, not a query surface — and it evolves with the form.
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    sources: Mapped[list[Source]] = relationship(back_populates="project", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="project", cascade="all, delete-orphan")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Source(Base):
    """Raw, immutable input evidence. Everything an agent claims must trace back here."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind))
    title: Mapped[str] = mapped_column(String(300), default="")
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    external_ref: Mapped[str | None] = mapped_column(String(400), nullable=True)  # gmail msg id / drive file id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="sources")


class Artifact(Base):
    """Logical artifact. Content lives in ArtifactVersion — artifacts are never overwritten."""

    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("project_id", "type", name="uq_artifact_project_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType))
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="artifacts")
    versions: Mapped[list[ArtifactVersion]] = relationship(
        back_populates="artifact", cascade="all, delete-orphan", order_by="ArtifactVersion.version"
    )


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (UniqueConstraint("artifact_id", "version", name="uq_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)            # structured, schema-validated
    rendered_md: Mapped[str] = mapped_column(Text, default="")  # human-readable render
    produced_by: Mapped[str] = mapped_column(String(60))   # agent id
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    model: Mapped[str] = mapped_column(String(80), default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    external_ref: Mapped[str | None] = mapped_column(String(400), nullable=True)  # drive/figma/jira url
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    artifact: Mapped[Artifact] = relationship(back_populates="versions")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)  # LangGraph checkpoint thread
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.PENDING)
    current_node: Mapped[str] = mapped_column(String(60), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="runs")
    events: Mapped[list[RunEvent]] = relationship(back_populates="run", cascade="all, delete-orphan")


class OutboundEmail(Base):
    """Every approval email the platform triggered.

    In memory this was lost on every restart — and Render restarts on each deploy and after idle —
    so the Approval Outbox would be empty while a gate sat waiting, with no way to reach the email.
    Approvals live in the database; their emails should too.
    """

    __tablename__ = "outbound_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(String(64), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), default="")
    to_addrs: Mapped[list] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(Text, default="")
    html: Mapped[str] = mapped_column(Text, default="")
    delivery: Mapped[str] = mapped_column(String(20), default="mock")   # mock | smtp | gmail
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RunEvent(Base):
    """Append-only audit trail. RBI/IT-governance auditors read this table."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    node: Mapped[str] = mapped_column(String(60))
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[Run] = relationship(back_populates="events")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    gate: Mapped[str] = mapped_column(String(60))          # e.g. concept_note_gate
    round: Mapped[int] = mapped_column(Integer, default=1)  # gates can be re-run after a revision
    artifact_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approver_email: Mapped[str] = mapped_column(String(200))
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    # Signed JWT. Length varies with claims — never cap it. Postgres enforces VARCHAR
    # limits (SQLite does not), so a String(n) here is a production-only landmine.
    token: Mapped[str] = mapped_column(Text, index=True)
    email_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    comments: Mapped[list[ApprovalComment]] = relationship(
        back_populates="approval", cascade="all, delete-orphan"
    )


class ApprovalComment(Base):
    __tablename__ = "approval_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id", ondelete="CASCADE"), index=True)
    author: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    anchor: Mapped[str] = mapped_column(String(200), default="")  # section the comment targets
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    approval: Mapped[Approval] = relationship(back_populates="comments")
