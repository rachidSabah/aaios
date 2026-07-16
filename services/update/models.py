"""Update manager models — Pydantic definitions for the enterprise update manager."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ReleaseChannel(StrEnum):
    """AAiOS release channels."""

    STABLE = "stable"
    LTS = "lts"
    BETA = "beta"
    NIGHTLY = "nightly"
    ENTERPRISE = "enterprise"


class UpdateStatus(StrEnum):
    """Current state of an update operation."""

    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


class UpdateInfo(BaseModel):
    """Details of an available update."""

    version: str
    channel: ReleaseChannel
    release_notes: str
    package_url: str
    size_bytes: int
    checksum: str
    force_upgrade: bool = False
    is_delta: bool = False


class UpdateReport(BaseModel):
    """Report summarizing the upgrade attempt."""

    id: str
    target_version: str
    channel: ReleaseChannel
    status: UpdateStatus = UpdateStatus.IDLE
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    migrated_components: list[str] = Field(default_factory=list)
    rollback_done: bool = False
    error: str | None = None
