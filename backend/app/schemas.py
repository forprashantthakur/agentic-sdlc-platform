from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import ApprovalStatus, ArtifactType, RunStatus, SourceKind


class SourceIn(BaseModel):
    kind: SourceKind
    title: str = ""
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class BusinessContext(BaseModel):
    """Screen 1 — the structured intake that feeds Agent 1."""

    business_owner: str = ""
    project_sponsor: str = ""
    priority: str = "Medium"
    business_objective: str = ""
    problem_statement: str = ""
    current_challenges: str = ""
    desired_outcome: str = ""
    expected_benefits: str = ""
    business_kpis: list[str] = Field(default_factory=list)
    estimated_business_value: str = ""
    timeline: str = ""
    budget: str = ""
    regulatory_scope: list[str] = Field(default_factory=list)


class ProjectIn(BaseModel):
    name: str
    business_unit: str = "Retail Banking"
    description: str = ""
    context: BusinessContext = Field(default_factory=BusinessContext)
    sources: list[SourceIn] = Field(default_factory=list)


class ProjectOut(BaseModel):
    id: str
    name: str
    business_unit: str
    description: str
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    source_count: int = 0
    run_count: int = 0
    artifact_count: int = 0
    status: str = "DRAFT"

    model_config = {"from_attributes": True}


class RunIn(BaseModel):
    project_id: str
    approvers: list[EmailStr]
    velocity: int = 15
    base_url: str = "http://localhost:5173"


class RunOut(BaseModel):
    id: str
    project_id: str
    thread_id: str
    status: RunStatus
    current_node: str
    error: str
    started_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: int
    node: str
    level: str
    message: str
    data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionOut(BaseModel):
    id: str
    version: int
    produced_by: str
    model: str
    approved: bool
    change_summary: str
    external_ref: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactOut(BaseModel):
    id: str
    type: ArtifactType
    current_version: int
    versions: list[VersionOut]

    model_config = {"from_attributes": True}


class VersionDetail(VersionOut):
    payload: dict[str, Any]
    rendered_md: str


class CommentIn(BaseModel):
    author: str
    body: str
    anchor: str = ""


class DecisionIn(BaseModel):
    decision: ApprovalStatus
    comments: list[CommentIn] = Field(default_factory=list)


class ApprovalOut(BaseModel):
    id: str
    project_id: str
    run_id: str
    gate: str
    round: int
    artifact_version_id: str | None
    approver_email: str
    status: ApprovalStatus
    created_at: datetime
    decided_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
