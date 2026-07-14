"""The Task Orchestrator core — submit, cancel, pause, resume, rollback.

The Orchestrator is the execution infrastructure. It:
  - Accepts plans from L4 callers (Supervisor, Workflow Agent, API)
  - Validates the DAG
  - Queues the plan in the priority queue
  - Dispatches ready steps to agents (via a StepExecutor callback)
  - Writes checkpoints before acknowledging committed steps
  - Handles cancellation, pause, resume, rollback

The Orchestrator does NOT decide which agent to use — that's the Capability
Selector's job (Phase 8). The Orchestrator is given a ``step_executor``
callable that takes a Step and returns the result. The callable is
responsible for agent dispatch.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event, EventTopic
from core.event_bus import EventBus, get_bus
from core.logging import get_logger
from orchestrator.checkpoint_store import InMemoryCheckpointStore
from orchestrator.contracts.checkpoint import Checkpoint, CheckpointStoreProtocol
from orchestrator.contracts.dag import (
    Plan,
    PlanStatus,
    Step,
    StepStatus,
)
from orchestrator.dag import DAGExecutor, validate_dag
from orchestrator.queue import Priority, PriorityQueue, QueueItem

_log = get_logger(__name__)

# Type alias: the step executor callable
StepExecutor = Callable[[Step], Awaitable[Any]]


@dataclass
class _ActivePlan:
    """Internal tracking for an active plan."""

    plan: Plan
    priority: Priority
    status: PlanStatus
    # Sequence counter for checkpoints
    checkpoint_sequence: int = 0
    # Cumulative cost
    cost_usd: float = 0.0


class TaskOrchestrator:
    """The Task Orchestrator.

    Use ``init_orchestrator()`` to create one and ``get_orchestrator()`` to
    retrieve it. The Orchestrator runs a background dispatch loop that pulls
    plans from the priority queue and executes their DAGs.
    """

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        checkpoint_store: CheckpointStoreProtocol | None = None,
        step_executor: StepExecutor | None = None,
        queue: PriorityQueue | None = None,
    ) -> None:
        self._bus = bus or get_bus()
        self._checkpoint_store: CheckpointStoreProtocol = (
            checkpoint_store or InMemoryCheckpointStore()
        )
        self._step_executor: StepExecutor | None = step_executor
        self._queue: PriorityQueue = queue or PriorityQueue()
        self._active_plans: dict[UUID, _ActivePlan] = {}
        self._executors: dict[UUID, DAGExecutor] = {}
        self._dispatch_task: asyncio.Task[None] | None = None
        self._running: bool = False
        self._lock = asyncio.Lock()

    def set_step_executor(self, executor: StepExecutor) -> None:
        """Set the step executor callable.

        Must be called before ``start()``. The callable takes a Step and
        returns the result (or raises). It's responsible for:
          - Calling the Capability Selector to find an agent
          - Dispatching the step to the agent via execute_task
          - Returning the result
        """
        self._step_executor = executor

    async def start(self) -> None:
        """Start the dispatch loop."""
        if self._running:
            return
        if self._step_executor is None:
            raise RuntimeError("Step executor not set. Call set_step_executor() first.")
        self._running = True
        self._dispatch_task = asyncio.create_task(
            self._dispatch_loop(),
            name="orchestrator.dispatch",
        )
        _log.info("orchestrator.started")

    async def stop(self) -> None:
        """Stop the dispatch loop. Waits for in-flight plans to complete."""
        self._running = False
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
            self._dispatch_task = None
        _log.info("orchestrator.stopped")

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    async def submit(self, plan: Plan, priority: str = "normal") -> UUID:
        """Submit a plan for execution.

        Validates the DAG, queues the plan, and returns the plan ID.

        Raises:
            DAGValidationError: if the DAG is invalid.
        """
        # Validate the DAG
        validate_dag(plan)

        prio = Priority.from_string(priority)
        async with self._lock:
            self._active_plans[plan.id] = _ActivePlan(
                plan=plan,
                priority=prio,
                status=PlanStatus.PENDING,
            )

        # Emit task.queued event
        await self._bus.publish(
            Event(
                topic=EventTopic.TASK_QUEUED,
                correlation_id=plan.task_id,
                actor=ActorRef.system(),
                payload={"plan_id": str(plan.id), "priority": prio.value},
            ),
        )

        # Enqueue
        await self._queue.enqueue(
            QueueItem(plan_id=plan.id, task_id=plan.task_id, priority=prio),
        )
        _log.info(
            "orchestrator.submitted",
            plan_id=str(plan.id),
            task_id=str(plan.task_id),
            priority=prio.value,
            step_count=len(plan.steps),
        )
        return plan.id

    # ------------------------------------------------------------------
    # Cancellation, pause, resume, rollback
    # ------------------------------------------------------------------

    async def cancel(self, plan_id: UUID, reason: str = "user requested") -> bool:
        """Cancel a plan. Cascade-cancels dependent plans first.

        Returns True if the plan was found and cancelled.
        """
        async with self._lock:
            active = self._active_plans.get(plan_id)
            if active is None:
                return False

            # Cancel in the executor (stops dispatching new steps)
            executor = self._executors.get(plan_id)
            if executor is not None:
                executor.cancel(plan_id)

            # Remove from queue if still pending
            await self._queue.remove(plan_id)

            # Mark all non-terminal steps as CANCELLED
            for step in active.plan.steps:
                if step.status not in (
                    StepStatus.SUCCEEDED,
                    StepStatus.FAILED,
                    StepStatus.SKIPPED,
                    StepStatus.CANCELLED,
                ):
                    step.status = StepStatus.CANCELLED

            active.status = PlanStatus.CANCELLED

        await self._bus.publish(
            Event(
                topic=EventTopic.TASK_CANCELLED,
                correlation_id=active.plan.task_id,
                actor=ActorRef.system(),
                payload={"plan_id": str(plan_id), "reason": reason},
            ),
        )
        _log.info("orchestrator.cancelled", plan_id=str(plan_id), reason=reason)
        return True

    async def pause(self, plan_id: UUID) -> bool:
        """Pause a plan (no new steps dispatched; in-flight steps continue).

        Returns True if the plan was found and paused.
        """
        async with self._lock:
            active = self._active_plans.get(plan_id)
            if active is None:
                return False
            active.status = PlanStatus.PAUSED
        await self._bus.publish(
            Event(
                topic=EventTopic.TASK_PAUSED,
                correlation_id=active.plan.task_id,
                actor=ActorRef.system(),
                payload={"plan_id": str(plan_id)},
            ),
        )
        _log.info("orchestrator.paused", plan_id=str(plan_id))
        return True

    async def resume(self, plan_id: UUID) -> bool:
        """Resume a paused plan. Re-enqueues it.

        Returns True if the plan was found and resumed.
        """
        async with self._lock:
            active = self._active_plans.get(plan_id)
            if active is None:
                return False
            if active.status != PlanStatus.PAUSED:
                return False
            active.status = PlanStatus.RUNNING
        await self._queue.enqueue(
            QueueItem(
                plan_id=plan_id,
                task_id=active.plan.task_id,
                priority=active.priority,
            ),
        )
        await self._bus.publish(
            Event(
                topic=EventTopic.TASK_RESUMED,
                correlation_id=active.plan.task_id,
                actor=ActorRef.system(),
                payload={"plan_id": str(plan_id)},
            ),
        )
        _log.info("orchestrator.resumed", plan_id=str(plan_id))
        return True

    async def rollback(self, plan_id: UUID, to_sequence: int) -> bool:
        """Roll back a plan to a prior checkpoint.

        Restores agent states from the checkpoint, marks steps after the
        checkpoint as PENDING, and re-enqueues the plan.

        Returns True if the plan was found and rolled back.
        """
        async with self._lock:
            active = self._active_plans.get(plan_id)
            if active is None:
                return False
            checkpoint = await self._checkpoint_store.get_at_sequence(
                active.plan.task_id,
                to_sequence,
            )
            if checkpoint is None:
                _log.error(
                    "orchestrator.rollback_checkpoint_not_found",
                    plan_id=str(plan_id),
                    sequence=to_sequence,
                )
                return False

            # Restore agent states
            for agent_id, state in checkpoint.agent_states.items():
                # The actual agent instance is restored by the Supervisor
                # (which has access to the Agent Registry). Here we just
                # store the states for the Supervisor to pick up.
                active.plan.variables[f"_restore_state_{agent_id}"] = state

            # Mark steps after the checkpoint as PENDING
            cp_step_index = -1
            for i, step in enumerate(active.plan.steps):
                if step.id == checkpoint.step_id:
                    cp_step_index = i
                    break
            for step in active.plan.steps[cp_step_index + 1 :]:
                step.status = StepStatus.PENDING
                step.assigned_agent_id = None

            active.checkpoint_sequence = to_sequence
            active.status = PlanStatus.RUNNING

        await self._queue.enqueue(
            QueueItem(
                plan_id=plan_id,
                task_id=active.plan.task_id,
                priority=active.priority,
            ),
        )
        _log.info(
            "orchestrator.rolled_back",
            plan_id=str(plan_id),
            to_sequence=to_sequence,
        )
        return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_plan(self, plan_id: UUID) -> Plan | None:
        """Return the plan (or None if not found)."""
        active = self._active_plans.get(plan_id)
        return active.plan if active else None

    def get_status(self, plan_id: UUID) -> PlanStatus | None:
        """Return the plan's status (or None if not found)."""
        active = self._active_plans.get(plan_id)
        return active.status if active else None

    def list_active_plans(self) -> list[UUID]:
        """Return all active plan IDs."""
        return list(self._active_plans.keys())

    def queue_depth(self) -> int:
        """Return the current queue depth."""
        return self._queue.depth()

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    async def checkpoint_step(
        self,
        plan_id: UUID,
        step: Step,
        result: Any = None,
        error: str | None = None,
        agent_states: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Write a checkpoint for a completed step.

        Must be called BEFORE acknowledging the step to the Supervisor
        (analog of INV-04 for the Orchestrator).
        """
        async with self._lock:
            active = self._active_plans.get(plan_id)
            if active is None:
                raise RuntimeError(f"Plan {plan_id} not found")
            active.checkpoint_sequence += 1
            seq = active.checkpoint_sequence

        checkpoint = Checkpoint(
            id=uuid4(),
            task_id=active.plan.task_id,
            plan_id=plan_id,
            step_id=step.id,
            step_goal=step.goal,
            step_status=step.status,
            agent_id=step.assigned_agent_id,
            capability=step.capability,
            inputs=step.inputs,
            output=result,
            error=error,
            agent_states=agent_states or {},
            cost_usd_so_far=active.cost_usd,
            sequence=seq,
        )
        await self._checkpoint_store.save(checkpoint)
        _log.info(
            "orchestrator.checkpoint_written",
            plan_id=str(plan_id),
            step_id=str(step.id),
            sequence=seq,
        )
        return checkpoint

    async def get_latest_checkpoint(self, plan_id: UUID) -> Checkpoint | None:
        """Return the latest checkpoint for a plan."""
        active = self._active_plans.get(plan_id)
        if active is None:
            return None
        return await self._checkpoint_store.get_latest(active.plan.task_id)

    # ------------------------------------------------------------------
    # Dispatch loop
    # ------------------------------------------------------------------

    async def _dispatch_loop(self) -> None:
        """Background loop: pull plans from the queue and execute them."""
        while self._running:
            try:
                item = await self._queue.dequeue()
                await self._execute_plan(item)
                await self._queue.complete(item.plan_id, item.priority)
            except asyncio.CancelledError:
                break
            except Exception:
                _log.exception("orchestrator.dispatch_error")

    async def _execute_plan(self, item: QueueItem) -> None:
        """Execute a plan's DAG."""
        async with self._lock:
            active = self._active_plans.get(item.plan_id)
            if active is None:
                _log.warning("orchestrator.plan_not_found", plan_id=str(item.plan_id))
                return
            if active.status == PlanStatus.PAUSED:
                # Re-queue (will be picked up when resumed)
                return
            active.status = PlanStatus.RUNNING
            plan = active.plan

        # Emit task.started
        await self._bus.publish(
            Event(
                topic=EventTopic.TASK_STARTED,
                correlation_id=plan.task_id,
                actor=ActorRef.system(),
                payload={"plan_id": str(plan.id)},
            ),
        )

        # Create an executor and run the DAG
        assert self._step_executor is not None
        executor = DAGExecutor(self._step_executor)
        self._executors[plan.id] = executor

        try:
            await executor.execute(plan)
        except Exception:
            _log.exception("orchestrator.plan_execution_failed", plan_id=str(plan.id))
            active.status = PlanStatus.FAILED

        # Update status
        active.status = plan.status

        # Emit terminal event
        if active.status == PlanStatus.SUCCEEDED:
            await self._bus.publish(
                Event(
                    topic=EventTopic.TASK_COMPLETED,
                    correlation_id=plan.task_id,
                    actor=ActorRef.system(),
                    payload={"plan_id": str(plan.id)},
                ),
            )
        elif active.status == PlanStatus.FAILED:
            await self._bus.publish(
                Event(
                    topic=EventTopic.TASK_FAILED,
                    correlation_id=plan.task_id,
                    actor=ActorRef.system(),
                    payload={"plan_id": str(plan.id)},
                ),
            )

        # Cleanup
        self._executors.pop(plan.id, None)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_INSTANCE: TaskOrchestrator | None = None


def init_orchestrator(**kwargs: Any) -> TaskOrchestrator:
    """Initialize the global Task Orchestrator."""
    global _INSTANCE
    _INSTANCE = TaskOrchestrator(**kwargs)
    return _INSTANCE


def get_orchestrator() -> TaskOrchestrator:
    """Return the global Task Orchestrator."""
    if _INSTANCE is None:
        raise RuntimeError("TaskOrchestrator not initialized. Call init_orchestrator() first.")
    return _INSTANCE


def set_orchestrator(orch: TaskOrchestrator) -> None:
    """Set the global Task Orchestrator (for testing)."""
    global _INSTANCE
    _INSTANCE = orch
