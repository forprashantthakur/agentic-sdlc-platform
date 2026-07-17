"""Gmail API — approval emails out, reviewer comments in.

Threading matters: every approval round keeps the same `threadId`, so a reviewer's
"looks good, but tighten BRULE-03" reply lands back on the right gate and is parsed
into an ApprovalComment rather than being lost in an inbox.
"""

from __future__ import annotations

import base64
import re
import uuid
from email.mime.text import MIMEText
from typing import Any

from app.core.config import settings
from app.core.logging import log
from app.adapters import outbox

DECISION_RE = re.compile(r"\b(APPROVE[D]?|REJECT(?:ED)?|CHANGES?\s+REQUESTED)\b", re.I)


def parse_decision(body: str) -> str | None:
    m = DECISION_RE.search(body or "")
    if not m:
        return None
    tok = m.group(1).upper()
    if tok.startswith("APPROVE"):
        return "APPROVED"
    if tok.startswith("REJECT"):
        return "REJECTED"
    return "CHANGES_REQUESTED"


class GmailAdapter:
    def __init__(self, sa_json: str, sender: str) -> None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            sa_json,
            scopes=["https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/gmail.readonly"],
        ).with_subject(sender)  # domain-wide delegation: send *as* the SDLC bot
        self.svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self.sender = sender

    def send(self, *, to, subject, html, thread_id=None) -> dict[str, Any]:
        msg = MIMEText(html, "html")
        msg["to"] = ", ".join(to)
        msg["from"] = self.sender
        msg["subject"] = subject
        body: dict[str, Any] = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        if thread_id:
            body["threadId"] = thread_id
        sent = self.svc.users().messages().send(userId="me", body=body).execute()
        outbox.record(to=to, subject=subject, html=html, thread_id=thread_id,
                      message_id=sent.get("id"), delivery="gmail")
        return {"message_id": sent["id"], "thread_id": sent["threadId"]}

    def fetch_replies(self, *, thread_id) -> list[dict[str, Any]]:
        th = self.svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
        out = []
        for m in th.get("messages", [])[1:]:  # skip our own outbound message
            headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
            out.append(
                {
                    "from": headers.get("from", ""),
                    "body": _extract_text(m["payload"]),
                    "received_at": headers.get("date", ""),
                }
            )
        return out


def _extract_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(errors="ignore")
    for part in payload.get("parts", []) or []:
        t = _extract_text(part)
        if t:
            return t
    return ""


class MockGmailAdapter:
    """Records outbound mail to the shared outbox (app.adapters.outbox) so the UI can render an
    Approval Outbox in the demo. Nothing is delivered — the email is captured and shown in-app."""

    def send(self, *, to, subject, html, thread_id=None) -> dict[str, Any]:
        rec = outbox.record(to=to, subject=subject, html=html, thread_id=thread_id, delivery="mock")
        log.info("gmail.mock.send", to=to, subject=subject)
        return {"message_id": rec["message_id"], "thread_id": rec["thread_id"]}

    def fetch_replies(self, *, thread_id) -> list[dict[str, Any]]:
        return []  # in the demo, decisions arrive via the API/UI, not by mail poll


class SmtpMailAdapter:
    """Real email over plain SMTP — the low-friction way to make an approval land in a real inbox.

    Chosen over Gmail domain-wide delegation because a demo needs one env block and an app password,
    not a Workspace admin granting service-account scopes. A send failure NEVER fails the run: the
    approval still exists in the app, the email is only a notification, so we record the attempt (with
    the error) to the Outbox and carry on. Resilience over drama.
    """

    def __init__(self) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.sender = settings.smtp_from or settings.smtp_user
        self.use_tls = settings.smtp_use_tls

    def send(self, *, to, subject, html, thread_id=None) -> dict[str, Any]:
        import smtplib
        from email.mime.multipart import MIMEMultipart

        recipients = to if isinstance(to, list) else [to]
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as srv:
                if self.use_tls:
                    srv.starttls()
                if self.user:
                    srv.login(self.user, self.password)
                srv.sendmail(self.sender, recipients, msg.as_string())
            rec = outbox.record(to=recipients, subject=subject, html=html, thread_id=thread_id,
                                delivery="smtp")
            log.info("smtp.send", to=recipients, subject=subject)
            return {"message_id": rec["message_id"], "thread_id": rec["thread_id"]}
        except Exception as e:  # never fail the run over a notification
            rec = outbox.record(to=recipients, subject=subject, html=html, thread_id=thread_id,
                                delivery="mock", error=f"SMTP send failed: {e}")
            log.warning("smtp.send_failed", error=str(e), to=recipients)
            return {"message_id": rec["message_id"], "thread_id": rec["thread_id"]}

    def fetch_replies(self, *, thread_id) -> list[dict[str, Any]]:
        return []  # inbound replies arrive via the /api/approvals/reply webhook, not SMTP polling
