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
    """Captures outbound mail in memory so the UI can render an 'Outbox' tab in the demo."""

    outbox: list[dict[str, Any]] = []

    def send(self, *, to, subject, html, thread_id=None) -> dict[str, Any]:
        tid = thread_id or uuid.uuid4().hex[:16]
        rec = {
            "message_id": uuid.uuid4().hex[:16],
            "thread_id": tid,
            "to": to,
            "subject": subject,
            "html": html,
        }
        MockGmailAdapter.outbox.append(rec)
        log.info("gmail.mock.send", to=to, subject=subject)
        return {"message_id": rec["message_id"], "thread_id": tid}

    def fetch_replies(self, *, thread_id) -> list[dict[str, Any]]:
        return []  # in the demo, decisions arrive via the API/UI, not by mail poll
