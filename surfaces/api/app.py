"""AAiOS API server (FastAPI).

Phase 2 stub: ``/healthz`` and ``/readyz`` only. Full API lands in Phase 12.
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="AAiOS API",
    description="Agentic AI Operating System — REST + WebSocket API.",
    version="0.1.0.dev0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class HealthResponse(BaseModel):
    """Response model for ``/healthz`` and ``/readyz``."""

    status: str
    version: str
    python: str
    platform: str
    timestamp: str
    checks: dict[str, str]


@app.get("/healthz", response_model=HealthResponse, tags=["health"])
async def healthz() -> HealthResponse:
    """Liveness probe — process is alive and the event loop is not stuck."""
    return HealthResponse(
        status="ok",
        version="0.1.0.dev0",
        python=sys.version.split()[0],
        platform=platform.platform(),
        timestamp=datetime.now(UTC).isoformat(),
        checks={
            "process": "alive",
            "event_loop": "ok",
        },
    )


@app.get("/readyz", response_model=HealthResponse, tags=["health"])
async def readyz() -> HealthResponse:
    """Readiness probe — process is alive and dependencies are reachable.

    Phase 2 stub: only checks the process. Real implementation (Phase 12)
    also checks Postgres, Qdrant, Redis (if configured), and the supervisor.
    """
    return HealthResponse(
        status="ok",
        version="0.1.0.dev0",
        python=sys.version.split()[0],
        platform=platform.platform(),
        timestamp=datetime.now(UTC).isoformat(),
        checks={
            "process": "alive",
            "database": "not_implemented",
            "qdrant": "not_implemented",
            "supervisor": "not_implemented",
        },
    )


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint — links to docs."""
    return {
        "name": "AAiOS API",
        "version": "0.1.0.dev0",
        "docs": "/docs",
        "health": "/healthz",
    }
