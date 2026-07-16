"""IntelligentSupervisor — v2.0 supervisor with adaptive routing, learning,
persistent planning, multi-agent collaboration, and autonomous jobs.

Upgrades the v1.0 DefaultSupervisor with:
- AdaptiveRouter (replaces CapabilitySelector for routing)
- ExecutionHistory (tracks every step for learning)
- SelfImprovingPolicy (adapts retry/correction limits)
- PersistentPlanner (plans survive reboots)
- DelegationManager (agents delegate to each other)
- AutonomousJobScheduler (long-running background jobs)

The v1.0 DefaultSupervisor is unchanged — this is a new class that
delegates to the v1.0 components where appropriate and adds v2.0
intelligence on top.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

from core.contracts.actor import ActorRef
from core.contracts.task import TaskContext, TaskId, TaskRequest, TaskResult, TaskResultStatus
from core.event_bus import EventBus, get_bus
from core.logging import get_logger
from orchestrator.contracts.dag import Plan, Step
from orchestrator.core import TaskOrchestrator
from services.agent_registry import AgentRegistry
from services.model_router import ModelRouter
from supervisor.correction import DefaultSelfCorrectionAgent
from supervisor.qa import DefaultQAAgent, QAVerdict
from supervisor.reflection import DefaultReflectionAgent, ReflectionVerdict
from supervisor.v2.adaptive_router import AdaptiveRouter
from supervisor.v2.autonomous_jobs import AutonomousJobScheduler
from supervisor.v2.delegation import DelegationManager
from supervisor.v2.execution_history import ExecutionHistory, ExecutionOutcome, ExecutionRecord
from supervisor.v2.persistent_planner import PersistentPlanner
from supervisor.v2.self_improving import SelfImprovingPolicy

_log = get_logger(__name__)

__all__ = ["IntelligentSupervisor"]


class IntelligentSupervisor:
    """v2.0 supervisor with learning, adaptation, and collaboration.

    Usage:
        supervisor = IntelligentSupervisor(
            registry=registry,
            orchestrator=orchestrator,
            router=router,
        )
        task_id = await supervisor.submit_goal('refactor auth module')
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        orchestrator: TaskOrchestrator,
        router: ModelRouter | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self._registry = registry
        self._orchestrator = orchestrator
        self._router = router
        self._bus = bus or get_bus()

        # v2.0 components
        self._history = ExecutionHistory()
        self._policy = SelfImprovingPolicy(self._history)
        self._router_adaptive = AdaptiveRouter(registry, self._history)
        self._planner = PersistentPlanner(router=router, bus=self._bus)
        self._delegator = DelegationManager(registry, self._router_adaptive)
        self._job_scheduler = AutonomousJobScheduler(bus=self._bus)

        # v1.0 components (reused)
        self._reflection = DefaultReflectionAgent(router=router)
        self._correction = DefaultSelfCorrectionAgent(router=router)
        self._qa = DefaultQAAgent(router=router)

        # Active task tracking
        self._active_tasks: dict[UUID, Plan] = {}
        self._results: dict[UUID, TaskResult] = {}

    @property
    def history(self) -> ExecutionHistory:
        """Return the execution history."""
        return self._history

    @property
    def policy(self) -> SelfImprovingPolicy:
        """Return the self-improving policy."""
        return self._policy

    @property
    def delegator(self) -> DelegationManager:
        """Return the delegation manager."""
        return self._delegator

    @property
    def job_scheduler(self) -> AutonomousJobScheduler:
        """Return the autonomous job scheduler."""
        return self._job_scheduler

    async def start(self) -> None:
        """Start the supervisor (including job scheduler)."""
        await self._job_scheduler.start()
        _log.info("intelligent_supervisor.started")

    async def stop(self) -> None:
        """Stop the supervisor."""
        await self._job_scheduler.stop()
        _log.info("intelligent_supervisor.stopped")

    async def submit_goal(
        self,
        goal: str,
        *,
        context: TaskContext | None = None,
        priority: str = "normal",
    ) -> TaskId:
        """Submit a goal for execution."""
        task_id = uuid4()

        # 1. Decompose the goal (with persistent planner)
        plan_result = await self._planner.decompose(goal, task_id)
        plan = plan_result.plan
        self._active_tasks[task_id] = plan

        _log.info(
            "intelligent_supervisor.goal_submitted",
            task_id=str(task_id),
            goal=goal,
            step_count=len(plan.steps),
        )

        # 2. Set up the step executor
        async def step_executor(step: Step) -> dict[str, Any]:
            return await self._execute_step(task_id, step)

        # 3. Submit to the orchestrator
        self._orchestrator.set_step_executor(step_executor)
        await self._orchestrator.submit(plan, priority=priority)

        return task_id

    async def _execute_step(self, task_id: UUID, step: Step) -> dict[str, Any]:
        """Execute a step with v2.0 intelligence: adaptive routing + learning."""
        start_time = time.monotonic()

        # 1. Select an agent using adaptive routing
        try:
            selection = self._router_adaptive.select(step.capability)
        except Exception as e:
            _log.error("intelligent_supervisor.no_agent", capability=step.capability, error=str(e))
            raise

        agent = self._registry.get(selection.agent_id)
        step.assigned_agent_id = selection.agent_id

        # 2. Build task request
        agent_request = TaskRequest(
            id=uuid4(),
            goal=step.goal,
            context=TaskContext(submitted_by=ActorRef.system()),
        )

        # 3. Execute with adaptive retry/correction limits
        max_corrections = self._policy.get_correction_limit(step.capability)
        _ = self._policy.get_retry_limit(step.capability)  # used for logging

        outcome = ExecutionOutcome.SUCCESS
        error_msg: str | None = None
        reflection_verdict = "accept"
        qa_verdict = "pass"
        correction_attempts = 0

        try:
            for attempt in range(max_corrections):
                result = await agent.execute_task(agent_request)  # type: ignore[attr-defined]

                if result.status == TaskResultStatus.SUCCESS:
                    # 4. Reflection
                    verdict, critique = await self._reflection.critique(
                        step_goal=step.goal,
                        agent_output=result.output,
                        success_criterion=step.success_criterion,
                    )
                    reflection_verdict = verdict.value

                    if verdict == ReflectionVerdict.ACCEPT:
                        # 5. QA
                        qa_v, qa_reason = await self._qa.validate(
                            deliverable=result.output,
                            success_criterion=step.success_criterion,
                        )
                        qa_verdict = qa_v.value

                        if qa_v == QAVerdict.PASS:
                            _log.info(
                                "intelligent_supervisor.step_passed",
                                task_id=str(task_id),
                                step_id=str(step.id),
                                agent=selection.agent_id,
                                attempt=attempt + 1,
                            )
                            self._correction.reset_attempts(str(step.id))

                            # 6. Record execution in history (LEARN)
                            latency_ms = (time.monotonic() - start_time) * 1000
                            await self._history.record(
                                ExecutionRecord(
                                    step_id=step.id,
                                    task_id=task_id,
                                    agent_id=selection.agent_id,
                                    capability=step.capability,
                                    outcome=outcome,
                                    cost_usd=result.cost_usd,
                                    latency_ms=latency_ms,
                                    reflection_verdict=reflection_verdict,
                                    qa_verdict=qa_verdict,
                                    correction_attempts=correction_attempts,
                                )
                            )

                            # 7. Update adaptive router + policy
                            self._router_adaptive.record_execution(step.capability)
                            self._policy.record_execution()

                            return {
                                "output": result.output,
                                "agent_id": selection.agent_id,
                                "attempts": attempt + 1,
                                "qa_reason": qa_reason,
                            }

                    # QA failed or reflection rejected — try correction
                    if self._correction.can_retry(str(step.id)):
                        corrected = await self._correction.correct(
                            step_goal=step.goal,
                            original_output=result.output,
                            critique=critique,
                            step_id=str(step.id),
                        )
                        correction_attempts += 1
                        agent_request = TaskRequest(
                            id=uuid4(),
                            goal=f"{step.goal}\n\nCorrection: {critique}\n\nCorrected: {corrected}",
                            context=TaskContext(submitted_by=ActorRef.system()),
                        )
                        continue
                    else:
                        raise RuntimeError(
                            f"Step {step.id} failed after {max_corrections} corrections"
                        )
                else:
                    if attempt < max_corrections - 1:
                        continue
                    outcome = ExecutionOutcome.FAILURE
                    error_msg = result.error or "Agent returned failure"
                    raise RuntimeError(f"Agent failed: {result.error}")

        except Exception as e:
            outcome = ExecutionOutcome.FAILURE
            error_msg = str(e)

            # Record failure in history
            latency_ms = (time.monotonic() - start_time) * 1000
            await self._history.record(
                ExecutionRecord(
                    step_id=step.id,
                    task_id=task_id,
                    agent_id=selection.agent_id,
                    capability=step.capability,
                    outcome=outcome,
                    latency_ms=latency_ms,
                    reflection_verdict=reflection_verdict,
                    qa_verdict=qa_verdict,
                    correction_attempts=correction_attempts,
                    metadata={"error": error_msg},
                )
            )
            self._router_adaptive.record_execution(step.capability)
            self._policy.record_execution()
            raise

        # Should not reach here
        raise RuntimeError(f"Step {step.id} exhausted all attempts")

    async def restore_after_reboot(self) -> list[Any]:
        """Restore incomplete plans after a reboot."""
        restored = await self._planner.restore_incomplete_plans()
        for rp in restored:
            if rp.needs_resume:
                self._active_tasks[uuid4()] = rp.plan  # Re-track
                _log.info(
                    "intelligent_supervisor.plan_restored",
                    plan_id=str(rp.plan.id),
                    steps=len(rp.plan.steps),
                )
        return restored

    def get_plan(self, task_id: TaskId) -> Plan | None:
        """Return the plan for a task."""
        return self._active_tasks.get(task_id)

    def get_execution_stats(self, capability: str | None = None) -> dict[str, Any]:
        """Return execution statistics (for dashboard)."""
        if capability:
            return self._history.get_capability_stats(capability)
        return {
            "total_executions": self._history.get_total_records(),
            "recent": len(self._history.get_recent_records(10)),
            "suggestions": len(self._policy.get_suggestions()),
            "adjustments": len(self._policy.get_adjustments()),
            "pending_delegations": len(self._delegator.get_pending_delegations()),
            "scheduled_jobs": len(self._job_scheduler.list_jobs()),
        }
