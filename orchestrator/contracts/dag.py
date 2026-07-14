"""Plan + Step + DAG contracts.

A Plan is a DAG of Steps. Each Step has:
  - An id (UUID)
  - A goal (natural language)
  - A capability requirement (NOT an agent name — INV-09)
  - A success criterion
  - A rollback hint
  - Dependencies (list of step IDs that must complete first)
  - An optional approval gate
  - A retry policy
  - A status (pending, running, succeeded, failed, skipped, retrying)

The DAG is validated at submission time: no cycles, no missing dependencies,
no unreachable steps.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.contracts.approval_gate import ApprovalGate
from orchestrator.contracts.retry import RetryPolicy

__all__ = [
    "DAGValidationError",
    "Plan",
    "PlanStatus",
    "Step",
    "StepStatus",
    "StepType",
]


class StepType(StrEnum):
    """The kind of step (for dashboard grouping)."""

    AGENT = "agent"  # dispatched to an agent via the Capability Selector
    APPROVAL = "approval"  # waits for a human approval
    WORKFLOW = "workflow"  # invokes a saved workflow
    BACKGROUND = "background"  # offloaded to the worker pool


class StepStatus(StrEnum):
    """Per-step lifecycle states."""

    PENDING = "pending"  # waiting for dependencies
    READY = "ready"  # dependencies met, waiting for dispatch
    RUNNING = "running"  # dispatched to an agent
    RETRYING = "retrying"  # failed, waiting for retry backoff
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"  # dependency failed; this step cannot run
    CANCELLED = "cancelled"
    PAUSED = "paused"  # waiting at an approval gate


class PlanStatus(StrEnum):
    """Plan-level lifecycle states."""

    PENDING = "pending"  # submitted, not yet started
    RUNNING = "running"
    PAUSED = "paused"  # awaiting approval or user action
    SUCCEEDED = "succeeded"  # all steps succeeded
    FAILED = "failed"  # at least one step failed
    CANCELLED = "cancelled"


class Step(BaseModel):
    """A single step in a Plan (a DAG node).

    The ``capability`` field is the namespace the Capability Selector uses
    to find a matching agent (e.g. ``code.read``). It is NEVER an agent
    implementation name (INV-09).

    Note: ``status`` is mutable during execution (PENDING → RUNNING →
    SUCCEEDED/FAILED/etc.). The other fields are effectively immutable
    after creation.
    """

    model_config = ConfigDict(frozen=False)  # status must be mutable

    id: UUID = Field(default_factory=uuid4)
    goal: str = Field(description="What this step should accomplish.")
    capability: str = Field(
        description="Capability namespace (e.g. ``code.read``). NOT an agent name.",
    )
    success_criterion: str = Field(
        default="",
        description="How QA evaluates this step (natural language or schema reference).",
    )
    rollback_hint: str = Field(default="", description="How to undo this step if needed.")
    depends_on: list[UUID] = Field(
        default_factory=list,
        description="Step IDs that must succeed before this step can run.",
    )
    step_type: StepType = Field(default=StepType.AGENT)
    approval_gate: ApprovalGate | None = Field(default=None)
    retry_policy: RetryPolicy | None = Field(default=None)
    # The agent_id chosen by the Capability Selector (filled at dispatch time)
    assigned_agent_id: str | None = Field(default=None)
    # Inputs (filled by the Planner or by prior step outputs)
    inputs: dict[str, Any] = Field(default_factory=dict)
    # Mutable: the step's current status (set by the executor)
    status: StepStatus = Field(default=StepStatus.PENDING)


class Plan(BaseModel):
    """A plan: a DAG of steps produced by the PlannerAgent.

    The Plan is submitted to the Task Orchestrator for execution. The
    Orchestrator validates the DAG, dispatches ready steps, tracks status,
    and emits events.
    """

    model_config = ConfigDict(frozen=False)  # status is mutable

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID = Field(description="The parent TaskRequest ID.")
    steps: list[Step] = Field(default_factory=list)
    status: PlanStatus = Field(default=PlanStatus.PENDING)
    # Workflow variables (inputs, outputs, intermediate values)
    variables: dict[str, Any] = Field(default_factory=dict)
    priority: str = Field(default="normal")

    def step_by_id(self, step_id: UUID) -> Step | None:
        """Return the step with ``step_id``, or None."""
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def step_index(self, step_id: UUID) -> int:
        """Return the index of the step with ``step_id``. Raises ValueError if not found."""
        for i, s in enumerate(self.steps):
            if s.id == step_id:
                return i
        raise ValueError(f"Step {step_id} not found in plan")

    def ready_steps(self) -> list[Step]:
        """Return steps whose dependencies are all SUCCEEDED and that are PENDING."""
        succeeded_ids = {s.id for s in self.steps if s.status == StepStatus.SUCCEEDED}
        ready: list[Step] = []
        for s in self.steps:
            if s.status != StepStatus.PENDING:
                continue
            if all(dep in succeeded_ids for dep in s.depends_on):
                ready.append(s)
        return ready

    def is_complete(self) -> bool:
        """Return True if all steps are in a terminal state."""
        terminal = {
            StepStatus.SUCCEEDED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
            StepStatus.CANCELLED,
        }
        return all(s.status in terminal for s in self.steps)


class DAGValidationError(ValueError):
    """Raised when a Plan's DAG is invalid (cycle, missing dep, unreachable step)."""

    def __init__(self, reason: str, step_id: UUID | None = None) -> None:
        super().__init__(f"{reason}" + (f" (step: {step_id})" if step_id else ""))
        self.reason = reason
        self.step_id = step_id
