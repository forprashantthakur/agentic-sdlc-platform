from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters import registry
from app.api import (
    approvals, artifacts, copilot, dashboard, integrations, memory, metrics, projects, runs,
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


@app.get("/health", tags=["ops"])
def health():
    """Reports exactly which integrations are live vs mocked — so nobody demos a 'live' run by accident."""
    return {"status": "ok", "env": settings.app_env, "integrations": registry.describe()}
