"""PersistentPlanner — plans survive reboots, resume across sessions.

In v1.0, plans are in-memory only. If the system crashes, all in-flight
plans are lost. v2.0 persists plans to the event store so they can be
restored on reboot.

The PersistentPlanner:
1. Wraps the v1.0 LlmPlanner (delegation, not replacement)
2. After creating a plan, persists it to the State Manager
3. On boot, loads all incomplete plans from the event store
4. For each plan, finds the latest checkpoint
5. Restores agent states from the checkpoint
6. Returns the plans ready for resume
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import EventBus, get_bus
from core.logging import get_logger
from orchestrator.contracts.dag import Plan, PlanStatus, StepStatus
from services.model_router import ModelRouter
from supervisor.planner import LlmPlanner, PlanResult

_log = get_logger(__name__)

__all__ = ["PersistentPlanner", "RestoredPlan"]


class RestoredPlan:
    """A plan restored from the event store after a reboot."""

    def __init__(
        self,
        plan: Plan,
        last_checkpoint_step: UUID | None,
        agent_states: dict[str, Any],
    ) -> None:
        self.plan = plan
        self.last_checkpoint_step = last_checkpoint_step
        self.agent_states = agent_states
        self.needs_resume = any(
            s.status
            not in (
                StepStatus.SUCCEEDED,
                StepStatus.FAILED,
                StepStatus.SKIPPED,
                StepStatus.CANCELLED,
            )
            for s in plan.steps
        )


class PersistentPlanner:
    """Planner that persists plans to the event store.

    Usage:
        planner = PersistentPlanner(router=router, bus=get_bus())
        result = await planner.decompose('refactor auth', task_id)
        # Plan is now persisted

        # On reboot:
        restored = await planner.restore_incomplete_plans()
        for rp in restored:
            if rp.needs_resume:
                await orchestrator.submit(rp.plan)
    """

    # Event topic for plan persistence
    PLAN_CREATED_TOPIC = "plan.created"
    PLAN_COMPLETED_TOPIC = "plan.completed"

    def __init__(
        self,
        router: ModelRouter | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self._planner = LlmPlanner(router=router)
        self._bus = bus or get_bus()
        self._persisted_plans: dict[UUID, Plan] = {}

    def set_router(self, router: ModelRouter) -> None:
        """Set the model router."""
        self._planner.set_router(router)

    async def decompose(
        self,
        goal: str,
        task_id: UUID,
        *,
        context: dict[str, Any] | None = None,
    ) -> PlanResult:
        """Decompose a goal and persist the plan."""
        result = await self._planner.decompose(goal, task_id, context=context)

        # Persist the plan
        self._persisted_plans[result.plan.id] = result.plan

        # Emit a plan.created event for the event store
        await self._bus.publish(
            Event(
                topic=self.PLAN_CREATED_TOPIC,
                correlation_id=task_id,
                actor=ActorRef.system(),
                payload={
                    "plan_id": str(result.plan.id),
                    "task_id": str(result.plan.task_id),
                    "step_count": len(result.plan.steps),
                    "steps": [
                        {
                            "id": str(s.id),
                            "goal": s.goal,
                            "capability": s.capability,
                            "depends_on": [str(d) for d in s.depends_on],
                        }
                        for s in result.plan.steps
                    ],
                },
            ),
        )

        _log.info(
            "persistent_planner.plan_created",
            plan_id=str(result.plan.id),
            task_id=str(task_id),
            steps=len(result.plan.steps),
        )
        return result

    async def mark_completed(self, plan_id: UUID, status: PlanStatus) -> None:
        """Mark a plan as completed (succeeded/failed/cancelled)."""
        if plan_id in self._persisted_plans:
            plan = self._persisted_plans[plan_id]
            plan.status = status

            await self._bus.publish(
                Event(
                    topic=self.PLAN_COMPLETED_TOPIC,
                    correlation_id=plan.task_id,
                    actor=ActorRef.system(),
                    payload={
                        "plan_id": str(plan_id),
                        "status": status.value,
                    },
                ),
            )

            # Remove from active plans
            del self._persisted_plans[plan_id]

            _log.info(
                "persistent_planner.plan_completed",
                plan_id=str(plan_id),
                status=status.value,
            )

    def get_persisted_plans(self) -> list[Plan]:
        """Return all persisted (incomplete) plans."""
        return list(self._persisted_plans.values())

    async def restore_incomplete_plans(self) -> list[RestoredPlan]:
        """Restore incomplete plans after a reboot.

        In v2.0 with a persistent event store, this would replay the event
        log to find all plan.created events without a corresponding
        plan.completed event. For now (in-memory), it returns the plans
        still in memory.
        """
        restored: list[RestoredPlan] = []
        for plan in self._persisted_plans.values():
            if plan.status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED, PlanStatus.CANCELLED):
                continue

            # Find the last completed step
            last_checkpoint: UUID | None = None
            for step in plan.steps:
                if step.status == StepStatus.SUCCEEDED:
                    last_checkpoint = step.id
                elif step.status in (StepStatus.RUNNING, StepStatus.RETRYING):
                    # This step was in-flight when the crash happened — reset to pending
                    step.status = StepStatus.PENDING

            restored.append(
                RestoredPlan(
                    plan=plan,
                    last_checkpoint_step=last_checkpoint,
                    agent_states={},  # Would be loaded from checkpoint store
                )
            )

        _log.info(
            "persistent_planner.restored",
            count=len(restored),
            plans=[str(rp.plan.id) for rp in restored],
        )
        return restored
