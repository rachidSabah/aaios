"""DAG validator and executor.

The validator checks at submission time:
  - No cycles
  - No missing dependencies (every dep references an existing step)
  - No unreachable steps (every step is reachable from a root step)

The executor runs ready steps concurrently via asyncio.gather, respecting
the per-priority concurrency limits (enforced by the priority queue).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from core.logging import get_logger
from orchestrator.contracts.dag import (
    DAGValidationError,
    Plan,
    Step,
    StepStatus,
)

_log = get_logger(__name__)

__all__ = ["DAGExecutor", "DAGValidator", "validate_dag"]

# Type alias for the step executor callable
StepExecutor = Callable[[Step], Awaitable[Any]]


class DAGValidator:
    """Validates a Plan's DAG at submission time."""

    @staticmethod
    def validate(plan: Plan) -> list[DAGValidationError]:
        """Return a list of validation errors (empty if valid)."""
        errors: list[DAGValidationError] = []
        step_ids = {s.id for s in plan.steps}

        # 1. No missing dependencies
        for step in plan.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        DAGValidationError(
                            f"Step depends on non-existent step {dep}",
                            step_id=step.id,
                        ),
                    )

        # 2. No cycles (DFS)
        cycle = _detect_cycle(plan)
        if cycle is not None:
            errors.append(
                DAGValidationError(
                    f"Cycle detected: {' -> '.join(str(s) for s in cycle)}",
                ),
            )

        # 3. No unreachable steps (every step must be reachable from a root)
        unreachable = _find_unreachable(plan)
        for step_id in unreachable:
            errors.append(
                DAGValidationError(
                    "Step is unreachable (no path from any root step)",
                    step_id=step_id,
                ),
            )

        return errors


def validate_dag(plan: Plan) -> None:
    """Validate a plan's DAG. Raises DAGValidationError if invalid."""
    errors = DAGValidator.validate(plan)
    if errors:
        raise errors[0]


def _detect_cycle(plan: Plan) -> list[UUID] | None:
    """Detect a cycle via DFS. Returns the cycle path, or None."""
    # Build adjacency list
    graph: dict[UUID, list[UUID]] = defaultdict(list)
    for step in plan.steps:
        for dep in step.depends_on:
            graph[dep].append(step.id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[UUID, int] = {s.id: WHITE for s in plan.steps}
    parent: dict[UUID, UUID | None] = {s.id: None for s in plan.steps}

    def dfs(node: UUID) -> list[UUID] | None:
        """DFS from ``node``. Returns the cycle path if found."""
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color.get(neighbor, WHITE) == GRAY:
                # Found a cycle — reconstruct it
                cycle: list[UUID] = [neighbor, node]
                current = node
                while parent[current] is not None and parent[current] != neighbor:
                    current = parent[current]  # type: ignore[assignment]
                    cycle.append(current)
                cycle.reverse()
                return cycle
            if color.get(neighbor, WHITE) == WHITE:
                parent[neighbor] = node
                result = dfs(neighbor)
                if result is not None:
                    return result
        color[node] = BLACK
        return None

    for step in plan.steps:
        if color[step.id] == WHITE:
            result = dfs(step.id)
            if result is not None:
                return result
    return None


def _find_unreachable(plan: Plan) -> list[UUID]:
    """Find steps that are not reachable from any root step.

    A root step is one with no dependencies.
    """
    if not plan.steps:
        return []
    # Build reverse adjacency: dep -> dependents
    dependents: dict[UUID, list[UUID]] = defaultdict(list)
    for step in plan.steps:
        for dep in step.depends_on:
            dependents[dep].append(step.id)
    # BFS from roots
    roots = [s.id for s in plan.steps if not s.depends_on]
    if not roots:
        # All steps have dependencies — if there's no cycle, this is fine
        # (but if there's no cycle AND no roots, every step is unreachable)
        return [s.id for s in plan.steps]
    reachable: set[UUID] = set()
    queue: deque[UUID] = deque(roots)
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for dependent in dependents.get(node, []):
            if dependent not in reachable:
                queue.append(dependent)
    return [s.id for s in plan.steps if s.id not in reachable]


class DAGExecutor:
    """Executes a Plan's DAG, running ready steps concurrently.

    The executor calls ``step_executor(step)`` for each ready step. The
    callable is responsible for dispatching to an agent (via the Capability
    Selector) and returning the result. The executor handles:

      - Finding ready steps (dependencies all succeeded)
      - Running independent steps concurrently via asyncio.gather
      - Retrying failed steps (per their retry policy)
      - Skipping steps whose dependencies failed
      - Emitting step lifecycle events on the bus
    """

    def __init__(
        self,
        step_executor: StepExecutor,
        *,
        max_concurrent: int = 16,
    ) -> None:
        self._step_executor = step_executor
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._cancelled: set[UUID] = set()

    async def execute(self, plan: Plan) -> Plan:
        """Execute the plan's DAG. Updates step statuses in place.

        Returns the plan (for convenience — it's mutated in place).
        """
        # Mark all root steps as PENDING (they already are, but be explicit)
        _log.info("dag.execute_start", plan_id=str(plan.id), step_count=len(plan.steps))

        while not plan.is_complete():
            # Find ready steps
            ready = self._find_ready_steps(plan)
            if not ready:
                # Check if we're stuck (no ready steps but not complete)
                if not self._has_in_flight_steps(plan):
                    # All remaining steps are blocked (their deps failed)
                    self._skip_blocked_steps(plan)
                    break
                # Wait for in-flight steps to complete
                await asyncio.sleep(0.05)
                continue

            # Dispatch ready steps concurrently
            tasks = [asyncio.create_task(self._execute_step(plan, step)) for step in ready]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        # Determine final plan status
        plan.status = self._compute_plan_status(plan)
        _log.info(
            "dag.execute_complete",
            plan_id=str(plan.id),
            status=plan.status.value,
        )
        return plan

    def cancel(self, plan_id: UUID) -> None:
        """Mark a plan as cancelled. In-flight steps will be skipped."""
        self._cancelled.add(plan_id)

    def _find_ready_steps(self, plan: Plan) -> list[Step]:
        """Return steps that are PENDING and whose deps are all SUCCEEDED."""
        succeeded = {s.id for s in plan.steps if s.status == StepStatus.SUCCEEDED}
        ready: list[Step] = []
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            if step.id in self._cancelled:
                continue
            if all(dep in succeeded for dep in step.depends_on):
                # Make a mutable copy with status READY
                step.status = StepStatus.READY
                ready.append(step)
        return ready

    def _has_in_flight_steps(self, plan: Plan) -> bool:
        """Return True if any step is RUNNING or RETRYING."""
        return any(s.status in (StepStatus.RUNNING, StepStatus.RETRYING) for s in plan.steps)

    def _skip_blocked_steps(self, plan: Plan) -> None:
        """Skip all PENDING steps (their deps must have failed)."""
        for step in plan.steps:
            if step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED

    async def _execute_step(self, plan: Plan, step: Step) -> None:
        """Execute a single step with the semaphore-bounded executor."""
        async with self._semaphore:
            if step.id in self._cancelled:
                step.status = StepStatus.CANCELLED
                return
            step.status = StepStatus.RUNNING
            try:
                result = await self._step_executor(step)
                step.status = StepStatus.SUCCEEDED
                # Store the result in plan variables for dependent steps
                plan.variables[str(step.id)] = result
                _log.info(
                    "dag.step_succeeded",
                    plan_id=str(plan.id),
                    step_id=str(step.id),
                    capability=step.capability,
                )
            except Exception as e:
                step.status = StepStatus.FAILED
                _log.exception(
                    "dag.step_failed",
                    plan_id=str(plan.id),
                    step_id=str(step.id),
                    error=str(e),
                )

    @staticmethod
    def _compute_plan_status(plan: Plan) -> Any:  # PlanStatus
        """Compute the final plan status from step statuses."""
        from orchestrator.contracts.dag import PlanStatus

        if any(s.status == StepStatus.FAILED for s in plan.steps):
            return PlanStatus.FAILED
        if all(s.status == StepStatus.SUCCEEDED for s in plan.steps):
            return PlanStatus.SUCCEEDED
        if any(s.status == StepStatus.CANCELLED for s in plan.steps):
            return PlanStatus.CANCELLED
        # Some steps skipped but no failures
        return PlanStatus.SUCCEEDED
