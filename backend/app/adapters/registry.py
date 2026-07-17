"""Credential-aware adapter selection.

One rule: if MOCK_MODE is on, or the credential for a given system is missing, that
system gets a mock. Systems are selected independently — you can run with a real
Gemini key and a mock Jira, which is exactly what you want during a POC.
"""

from __future__ import annotations

from functools import lru_cache

from app.adapters.figma_mcp import FigmaMCPAdapter, MockFigmaAdapter
from app.adapters.stitch import MockStitchAdapter, StitchAdapter
from app.adapters.gdrive import DriveAdapter, MockDriveAdapter
from app.adapters.gmail import GmailAdapter, MockGmailAdapter, SmtpMailAdapter
from app.adapters.jira import JiraAdapter, MockJiraAdapter
from app.core.config import settings
from app.core.logging import log


@lru_cache
def figma():
    if settings.is_mocked("figma") or not settings.figma_token:
        return MockFigmaAdapter()
    return FigmaMCPAdapter(settings.figma_mcp_url, settings.figma_token)


@lru_cache
def stitch():
    if settings.is_mocked("stitch") or not settings.stitch_api_key:
        return MockStitchAdapter()
    return StitchAdapter(settings.stitch_mcp_url, settings.stitch_api_key)


@lru_cache
def wireframer():
    """Agent 3's provider. Stitch by default; Figma if you specifically want frames in a Figma file.

    Both satisfy the same port, so Agent 3 does not know or care which one it is talking to.
    """
    provider = (settings.wireframe_provider or "stitch").lower()
    if provider == "figma":
        return figma()
    if provider == "mock":
        return MockStitchAdapter()
    return stitch()


@lru_cache
def mail():
    # Real send takes precedence when configured: SMTP (simplest) then Gmail service account.
    # is_mocked("gmail")=True forces the Outbox-only path regardless, for a guaranteed-safe demo.
    if not settings.is_mocked("gmail"):
        if settings.smtp_host:
            return SmtpMailAdapter()
        if settings.google_sa_json:
            return GmailAdapter(settings.google_sa_json, settings.gmail_sender)
    return MockGmailAdapter()


@lru_cache
def drive():
    if settings.is_mocked("drive") or not (settings.google_sa_json and settings.gdrive_root_folder_id):
        return MockDriveAdapter()
    return DriveAdapter(settings.google_sa_json, settings.gdrive_root_folder_id)


@lru_cache
def tracker():
    if settings.is_mocked("jira") or not (settings.jira_token and settings.jira_base_url):
        return MockJiraAdapter()
    return JiraAdapter(settings.jira_base_url, settings.jira_email, settings.jira_token)


def describe() -> dict[str, str]:
    """Surfaced on /health so nobody demos a 'live' run that was quietly mocked."""
    def name(o) -> str:
        return "mock" if type(o).__name__.startswith("Mock") else "live"

    from app.llm.gemini import gemini

    d = {
        "llm": "live" if gemini().live else "mock",
        "model": gemini().model_name,
        "wireframe_provider": settings.wireframe_provider,
        "wireframes": name(wireframer()),
        "figma": name(figma()),
        "gmail": name(mail()),
        "drive": name(drive()),
        "jira": name(tracker()),
    }
    log.info("adapters.describe", **d)
    return d
