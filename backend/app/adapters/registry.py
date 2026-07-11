"""Credential-aware adapter selection.

One rule: if MOCK_MODE is on, or the credential for a given system is missing, that
system gets a mock. Systems are selected independently — you can run with a real
Gemini key and a mock Jira, which is exactly what you want during a POC.
"""

from __future__ import annotations

from functools import lru_cache

from app.adapters.figma_mcp import FigmaMCPAdapter, MockFigmaAdapter
from app.adapters.gdrive import DriveAdapter, MockDriveAdapter
from app.adapters.gmail import GmailAdapter, MockGmailAdapter
from app.adapters.jira import JiraAdapter, MockJiraAdapter
from app.core.config import settings
from app.core.logging import log


@lru_cache
def figma():
    if settings.is_mocked("figma") or not settings.figma_token:
        return MockFigmaAdapter()
    return FigmaMCPAdapter(settings.figma_mcp_url, settings.figma_token)


@lru_cache
def mail():
    if settings.is_mocked("gmail") or not settings.google_sa_json:
        return MockGmailAdapter()
    return GmailAdapter(settings.google_sa_json, settings.gmail_sender)


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
        "figma": name(figma()),
        "gmail": name(mail()),
        "drive": name(drive()),
        "jira": name(tracker()),
    }
    log.info("adapters.describe", **d)
    return d
