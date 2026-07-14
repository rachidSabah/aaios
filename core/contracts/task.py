"""Task contracts — the basic unit of work in AAiOS.

A Task is a user-submitted goal that the Supervisor decomposes into a DAG
of Steps. Steps are dispatched to agents via the Capability Selector.

This module defines the *envelope* types (TaskRequest, TaskResult, etc.).
The richer types (Plan, Step, DAG) live in ``orchestrator.contracts``
because they're specific to the Task Orchestrator (L4), not the kernel (L1).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.actor import ActorRef
from core.contracts.timestamp import utc_now

# Type alias for clarity
TaskId = UUID


class TaskStatus(StrEnum):
    """Task lifecycle states."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"  # awaiting user input, approval gate, or external event
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskResultStatus(StrEnum):
    """Outcome of a task or step."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskContext(BaseModel):
    """The context in which a task runs.

    Includes the actor that submitted it, the project (memory scope), the
    allowed permissions, the budget, and a free-form metadata bag.
    """

    model_config = ConfigDict(extra="forbid")

    submitted_by: ActorRef
    project_id: str | None = Field(default=None, description="Memory scope.")
    budget_usd: float | None = Field(default=None, ge=0.0)
    timeout_s: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRequest(BaseModel):
    """A request to execute a task.

    Submitted by a surface (CLI, Web, API) to the Supervisor, or by the
    Supervisor to the Task Orchestrator.
    """

    model_config = ConfigDict(extra="forbid")

    id: TaskId = Field(default_factory=uuid4)
    goal: str = Field(description="Natural-language goal.")
    context: TaskContext
    priority: str = Field(default="normal", description="critical|high|normal|low|background")
    created_at: datetime = Field(default_factory=utc_now)


class TaskResult(BaseModel):
    """The result of executing a task (or step)."""

    model_config = ConfigDict(extra="forbid")

    task_id: TaskId
    status: TaskResultStatus
    output: Any = Field(default=None, description="The deliverable.")
    error: str | None = Field(default=None, description="Error message if status=FAILURE.")
    cost_usd: float = Field(default=0.0, ge=0.0)
    duration_s: float = Field(default=0.0, ge=0.0)
    completed_at: datetime = Field(default_factory=utc_now)


class TaskProgressKind(StrEnum):
    """The kind of a TaskProgress event."""

    STARTED = "started"
    INFO = "info"  # intermediate progress: "reading file 3 of 10"
    OUTPUT = "output"  # partial output
    WARNING = "warning"
    RESULT = "result"  # final — carries the TaskResult
    ERROR = "error"


class TaskProgress(BaseModel):
    """A progress event emitted by a long-running task.

    Streamed via ``GenericAgent.stream_progress()`` and surfaced on the
    dashboard via WebSocket.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: TaskId
    kind: TaskProgressKind
    message: str = Field(default="")
    progress_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=utc_now)
    result: TaskResult | None = Field(default=None, description="Present iff kind=RESULT.")


__all__ = [
    "TaskContext",
    "TaskId",
    "TaskProgress",
    "TaskProgressKind",
    "TaskRequest",
    "TaskResult",
    "TaskResultStatus",
    "TaskStatus",
]
