"""Backup and recovery models — Pydantic models for backup, restore, and snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class BackupType(StrEnum):
    """Supported backup strategy types."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class ExportFormat(StrEnum):
    """Supported export formats for backups."""

    ZIP = "zip"
    TAR = "tar"
    JSON = "json"
    JSONL = "jsonl"
    YAML = "yaml"


class BackupMetadata(BaseModel):
    """Metadata included with every backup or snapshot."""

    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    backup_type: BackupType
    format: ExportFormat
    version: str
    git_commit: str | None = None
    installed_providers: list[str] = Field(default_factory=list)
    installed_agents: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)
    database_versions: dict[str, int] = Field(default_factory=dict)
    platform_info: dict[str, str] = Field(default_factory=dict)
    environment_summary: dict[str, Any] = Field(default_factory=dict)
    checksums: dict[str, str] = Field(default_factory=dict)
    size_bytes: int = 0
    tags: list[str] = Field(default_factory=list)
    encrypted: bool = False


class RestoreReport(BaseModel):
    """Report generated after a restore operation."""

    id: str
    backup_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    success: bool = False
    restored_components: list[str] = Field(default_factory=list)
    validation_passed: bool = False
    compatibility_passed: bool = False
    errors: list[str] = Field(default_factory=list)
    rolled_back: bool = False
