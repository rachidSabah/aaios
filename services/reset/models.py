"""Reset models — Pydantic definitions for factory resets and rollbacks."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ResetConfig(BaseModel):
    """Configuration options for system reset."""

    factory: bool = False
    workspace: bool = False
    memory: bool = False
    providers: bool = False
    plugins: bool = False
    missions: bool = False
    database: bool = False
    everything: bool = False


class ResetReport(BaseModel):
    """Report generated after reset execution."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    backup_id: str | None = None
    reset_components: list[str] = Field(default_factory=list)
    success: bool = True
    error: str | None = None
