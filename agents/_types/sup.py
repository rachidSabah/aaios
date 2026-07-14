"""SupervisorAgent — the orchestrator-in-chief.

Owns the task lifecycle. Calls the Planner, dispatches to specialized agents
via the Capability Selector, invokes Reflection, Self-Correction, and QA.

The Supervisor is itself an agent (implements GenericAgent). It can be
replaced with an alternative implementation that uses a different planning
or reflection strategy.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from agents._types.gen import GenericAgent
from core.contracts.task import TaskId, TaskResult


@runtime_checkable
class SupervisorAgent(GenericAgent, Protocol):
    """The Supervisor agent type.

    Capabilities advertised: ``supervise.task``, ``supervise.plan``,
    ``supervise.dispatch``, ``supervise.reflect``, ``supervise.correct``,
    ``supervise.qa``.
    """

    async def submit_goal(self, goal: str, *, priority: str = "normal") -> TaskId:
        """Accept a natural-language goal from a user surface.

        Returns the new task ID. The supervisor decomposes the goal (via a
        PlannerAgent), submits the plan to the Task Orchestrator, and
        tracks it through to completion.
        """
        ...

    async def pause(self, task_id: TaskId) -> None:
        """Pause a running task. Idempotent."""
        ...

    async def resume(self, task_id: TaskId) -> None:
        """Resume a paused task. Idempotent."""
        ...

    async def rollback(self, task_id: TaskId, step_id: UUID) -> None:
        """Roll back a task to a prior checkpoint."""
        ...

    async def override(self, task_id: TaskId, decision: str) -> None:
        """Override the supervisor's decision (e.g. force a specific agent)."""
        ...

    async def get_result(self, task_id: TaskId) -> TaskResult | None:
        """Return the result of a completed task, or None if not done."""
        ...
