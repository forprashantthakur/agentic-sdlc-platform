from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters import registry
from app.api import (
    approvals, artifacts, copilot, dashboard, integrations, intake, memory, metrics, projects, runs,
)
from app.core.config import settings
from app.core.db import init_db
from app.core.logging import configure_logging, log


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    log.info("startup", env=settings.app_env, mock_mode=settings.mock_mode, **registry.describe())
    yield


app = FastAPI(
    title="HDFC Bank — Agentic AI SDLC Platform",
    description=(
        "Multi-agent requirement gathering and requirement documentation on Gemini 2.5 Pro. "
        "Six agents, two human approval gates, RAG-backed long-term memory, and full artifact versioning."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],   # so the browser can read the download filename
)

app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(artifacts.router)
app.include_router(approvals.router)
app.include_router(memory.router)
app.include_router(integrations.router)
app.include_router(dashboard.router)
app.include_router(copilot.router)
app.include_router(metrics.router)
app.include_router(intake.router)


@app.get("/health", tags=["ops"])
def health():
    """Reports exactly which integrations are live vs mocked — so nobody demos a 'live' run by accident.

    Also reports WHICH BUILD is running. Several diagnoses in this project were wasted on a fix that
    had not deployed yet, with no way to tell from the UI. Render sets RENDER_GIT_COMMIT; if a
    reported bug does not match the code, compare this first.
    """
    import os

    commit = (os.environ.get("RENDER_GIT_COMMIT")
              or os.environ.get("GIT_COMMIT")
              or os.environ.get("SOURCE_VERSION") or "")
    return {
        "status": "ok",
        "env": settings.app_env,
        "build": commit[:7] or "unknown",
        "build_full": commit,
        "integrations": registry.describe(),
    }
