"""Agent 5 — Approval Agent.

This agent is the reason the platform is safe to deploy inside a bank. It does four things:

  * renders a review packet and emails it to the named approvers (Gmail API, threaded);
  * persists a pending Approval row with a signed, expiring token per approver;
  * captures decisions and comments — from the email thread or the web console — into the
    audit trail;
  * hands the decision back to the graph so LangGraph's `interrupt` can either resume the
    workflow or route it back to the producing agent with the reviewer's comments attached.

It never decides anything itself. That is deliberate.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import select

from app.adapters import registry
from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.models import Approval, ApprovalStatus, ArtifactVersion

EMAIL_TMPL = """
<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:680px;color:#12263f">
  <div style="background:#004C8F;color:#fff;padding:18px 22px;border-radius:8px 8px 0 0">
    <div style="font-size:12px;letter-spacing:.12em;opacity:.85">HDFC BANK · AGENTIC SDLC PLATFORM</div>
    <div style="font-size:20px;font-weight:600;margin-top:4px">Approval required — {gate_label}</div>
  </div>
  <div style="border:1px solid #e3e8ef;border-top:0;padding:22px;border-radius:0 0 8px 8px">
    <p><strong>Project:</strong> {project}<br>
       <strong>Artifact:</strong> {artifact} (v{version})<br>
       <strong>Produced by:</strong> {agent} · <strong>Model:</strong> {model}</p>
    <p style="background:#f6f8fb;border-left:3px solid #004C8F;padding:10px 14px;margin:16px 0">
      {change_summary}
    </p>
    <h3 style="font-size:14px;margin:20px 0 8px">Summary of the artifact</h3>
    <pre style="background:#f6f8fb;padding:14px;border-radius:6px;font-size:12px;
                white-space:pre-wrap;max-height:420px;overflow:auto">{preview}</pre>
    <p style="margin-top:22px">
      <a href="{base}/approve?token={token}&decision=APPROVED"
         style="background:#00875A;color:#fff;padding:11px 20px;border-radius:6px;
                text-decoration:none;font-weight:600">Approve</a>
      &nbsp;
      <a href="{base}/approve?token={token}&decision=CHANGES_REQUESTED"
         style="background:#ED232A;color:#fff;padding:11px 20px;border-radius:6px;
                text-decoration:none;font-weight:600">Request changes</a>
    </p>
    <p style="font-size:12px;color:#6b7a90;margin-top:18px">
      Or simply reply to this email with <strong>APPROVED</strong> or <strong>CHANGES REQUESTED</strong>
      followed by your comments — the platform parses the thread and records your comments against
      this gate. This request expires in {ttl} hours.
    </p>
  </div>
</div>
"""

GATE_LABELS = {
    "concept_note_gate": "Concept Note sign-off",
    "requirement_docs_gate": "Requirement Documentation sign-off",
}


class ApprovalAgent(BaseAgent):
    id = "agent5_approval"
    name = "Approval Agent"

    def __init__(self, ctx, *, gate: str, artifact_version_id: str, approvers: list[str],
                 base_url: str = "http://localhost:5173") -> None:
        super().__init__(ctx)
        self.gate = gate
        self.artifact_version_id = artifact_version_id
        self.approvers = approvers
        self.base_url = base_url

    def run(self) -> AgentResult:
        v = self.ctx.db.get(ArtifactVersion, self.artifact_version_id)
        if v is None:
            raise ValueError(f"Unknown artifact version {self.artifact_version_id}")

        # Each pass through a gate is its own round. Without this, a "changes requested" from
        # round 1 would still be counted when we tally round 2 and the gate could never pass.
        prior = self.ctx.db.scalars(
            select(Approval.round).where(
                Approval.run_id == self.ctx.run_id, Approval.gate == self.gate
            )
        ).all()
        rnd = (max(prior) + 1) if prior else 1

        expires = datetime.now(timezone.utc) + timedelta(hours=settings.approval_token_ttl_hours)
        approval_ids: list[str] = []

        for approver in self.approvers:
            token = jwt.encode(
                {
                    "sub": approver,
                    "run": self.ctx.run_id,
                    "gate": self.gate,
                    "ver": v.id,
                    "jti": secrets.token_urlsafe(8),
                    "exp": int(expires.timestamp()),
                },
                settings.jwt_secret,
                algorithm="HS256",
            )
            approval = Approval(
                project_id=self.ctx.project_id,
                run_id=self.ctx.run_id,
                gate=self.gate,
                round=rnd,
                artifact_version_id=v.id,
                approver_email=approver,
                status=ApprovalStatus.PENDING,
                token=token,
                expires_at=expires,
            )
            self.ctx.db.add(approval)
            self.ctx.db.flush()

            sent = registry.mail().send(
                to=[approver],
                subject=f"[HDFC SDLC] Approval required — {GATE_LABELS.get(self.gate, self.gate)} — {self.ctx.project_name}",
                html=EMAIL_TMPL.format(
                    gate_label=GATE_LABELS.get(self.gate, self.gate),
                    project=self.ctx.project_name,
                    artifact=v.artifact.type.value,
                    version=v.version,
                    agent=v.produced_by,
                    model=v.model,
                    change_summary=v.change_summary or "—",
                    preview=(v.rendered_md[:2500] + ("…" if len(v.rendered_md) > 2500 else ""))
                            .replace("<", "&lt;"),
                    base=self.base_url,
                    token=token,
                    ttl=settings.approval_token_ttl_hours,
                ),
            )
            approval.email_message_id = sent["message_id"]
            self.ctx.db.add(approval)
            approval_ids.append(approval.id)

        # Push the approved-artifact-to-be into Drive so reviewers can comment in-place.
        drive = registry.drive().upload_markdown(
            folder=self.ctx.project_name,
            name=f"{v.artifact.type.value}_v{v.version}.md",
            markdown=v.rendered_md,
        )

        return AgentResult(
            artifacts={},
            payloads={},
            external={"approval_ids": approval_ids, "drive": drive},
            notes=(
                f"Round {rnd}: approval requested from {len(self.approvers)} approver(s) "
                f"for {v.artifact.type.value} v{v.version}"
            ),
        )
