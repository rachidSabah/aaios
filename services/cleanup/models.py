"""Cleanup models — Pydantic definitions for space reclamation and pruning."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CleanupConfig(BaseModel):
    """Configuration options for system cleanup."""

    dry_run: bool = False
    all: bool = False
    cache: bool = False
    logs: bool = False
    backups: bool = False
    models: bool = False
    reports: bool = False


class CleanupReport(BaseModel):
    """Report generated after cleanup execution."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reclaimed_bytes: int = 0
    cleaned_items: list[str] = Field(default_factory=list)
    dry_run: bool = False
    success: bool = True
    error: str | None = None
