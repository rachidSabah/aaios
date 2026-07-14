"""Checkpoint — a durable record of a committed step.

Every committed step produces a Checkpoint. The Orchestrator writes it to
the checkpoint store BEFORE acknowledging the step to the Supervisor
(same invariant as INV-04 for events).

On crash recovery, the Orchestrator loads the latest checkpoint per task
and offers the Supervisor three options: resume, rollback to a prior
checkpoint, or abort.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.agent import AgentState
from core.contracts.task import TaskResultStatus
from core.contracts.timestamp import utc_now
from orchestrator.contracts.dag import StepStatus

__all__ = ["Checkpoint", "CheckpointStoreProtocol"]


class Checkpoint(BaseModel):
    """A durable record of a committed step.

    Contains everything needed to resume, audit, or roll back the task.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(description="Unique checkpoint ID.")
    task_id: UUID
    plan_id: UUID
    step_id: UUID
    step_goal: str
    step_status: StepStatus
    agent_id: str | None = Field(default=None, description="Agent that executed the step.")
    capability: str = Field(default="", description="Capability used.")
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: Any = Field(default=None)
    result_status: TaskResultStatus | None = Field(default=None)
    error: str | None = Field(default=None)
    # Per-agent state snapshots at checkpoint time (for restore_state on resume)
    agent_states: dict[str, AgentState] = Field(default_factory=dict)
    # Cumulative cost so far
    cost_usd_so_far: float = Field(default=0.0, ge=0.0)
    # Sequence number (monotonic per task)
    sequence: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class CheckpointStoreProtocol(Protocol):
    """The interface every checkpoint store implements.

    Implementations:
      - InMemoryCheckpointStore (default; for tests and ephemeral runs)
      - PersistentCheckpointStore (Phase 8+; backed by the event store)
    """

    async def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint. Must be durable before returning (INV-04 analog)."""
        ...

    async def get_latest(self, task_id: UUID) -> Checkpoint | None:
        """Return the latest checkpoint for ``task_id``, or None."""
        ...

    async def get_all(self, task_id: UUID) -> list[Checkpoint]:
        """Return all checkpoints for ``task_id``, in sequence order."""
        ...

    async def get_at_sequence(self, task_id: UUID, sequence: int) -> Checkpoint | None:
        """Return the checkpoint at the given sequence, or None."""
        ...

    async def list_tasks(self) -> list[UUID]:
        """Return all task IDs that have at least one checkpoint."""
        ...

    async def delete(self, task_id: UUID) -> int:
        """Delete all checkpoints for ``task_id``. Returns count deleted."""
        ...
