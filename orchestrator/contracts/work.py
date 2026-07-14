"""Background job contracts — for the worker pool."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.timestamp import utc_now

__all__ = ["BackgroundJob", "BackgroundJobResult", "BackgroundJobStatus"]

# Type alias for the background work callable
BackgroundWork = Callable[["BackgroundJob"], Awaitable[Any]]


class BackgroundJobStatus(StrEnum):
    """Background job lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundJob(BaseModel):
    """A background job submitted to the worker pool.

    The ``work`` callable is NOT serialized (it's a Python function); jobs
    are in-process only in v1. Multi-machine workers are a v1.1 feature.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(default="")
    status: BackgroundJobStatus = Field(default=BackgroundJobStatus.QUEUED)
    submitted_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # The work callable (excluded from serialization)
    work: Any = Field(default=None, exclude=True)
    # Inputs passed to the work callable
    inputs: dict[str, Any] = Field(default_factory=dict)
    # Result (set when the job completes)
    result: Any = Field(default=None)
    error: str | None = Field(default=None)
    # Progress (0.0 - 1.0), updated by the work callable
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    progress_message: str = Field(default="")
    # Optional timeout
    timeout_s: float | None = Field(default=None, ge=0.0)

    def mark_started(self) -> None:
        """Mark the job as started."""
        self.status = BackgroundJobStatus.RUNNING
        self.started_at = utc_now()

    def mark_succeeded(self, result: Any) -> None:
        """Mark the job as succeeded."""
        self.status = BackgroundJobStatus.SUCCEEDED
        self.result = result
        self.completed_at = utc_now()
        self.progress = 1.0

    def mark_failed(self, error: str) -> None:
        """Mark the job as failed."""
        self.status = BackgroundJobStatus.FAILED
        self.error = error
        self.completed_at = utc_now()

    def mark_cancelled(self) -> None:
        """Mark the job as cancelled."""
        self.status = BackgroundJobStatus.CANCELLED
        self.completed_at = utc_now()

    def update_progress(self, progress: float, message: str = "") -> None:
        """Update progress (called by the work callable)."""
        self.progress = min(1.0, max(0.0, progress))
        self.progress_message = message


class BackgroundJobResult(BaseModel):
    """The result of a completed background job (serializable)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: UUID
    status: BackgroundJobStatus
    result: Any = None
    error: str | None = None
    duration_s: float = 0.0
