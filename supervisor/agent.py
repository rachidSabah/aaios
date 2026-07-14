"""DefaultSupervisor — the main supervisor loop.

The Supervisor owns the task lifecycle. It:
  1. Accepts a goal from a user surface
  2. Calls the Planner to decompose it into a DAG plan
  3. Submits the plan to the Task Orchestrator
  4. For each step:
     a. Selects an agent via the Capability Selector
     b. Dispatches the step to the agent
     c. Calls Reflection on the output
     d. If rejected: calls Self-Correction and retries
     e. Calls QA to validate the deliverable
     f. If QA passes: commits the step (checkpoint)
  5. Returns the final result

The Supervisor itself is a GenericAgent (SupervisorAgent type). It can be
replaced with an alternative implementation that uses a different planning
or reflection strategy.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from core.contracts.actor import ActorRef
from core.contracts.task import (
    TaskContext,
    TaskId,
    TaskRequest,
    TaskResult,
    TaskResultStatus,
)
from core.logging import get_logger
from orchestrator.contracts.dag import Plan, PlanStatus, Step
from orchestrator.core import TaskOrchestrator
from services.agent_registry import AgentRegistry
from services.model_router import ModelRouter
from supervisor.capability_selector import CapabilitySelector, NoCandidateError
from supervisor.correction import DefaultSelfCorrectionAgent
from supervisor.planner import LlmPlanner
from supervisor.qa import DefaultQAAgent, QAVerdict
from supervisor.reflection import DefaultReflectionAgent, ReflectionVerdict

_log = get_logger(__name__)

__all__ = ["DefaultSupervisor"]


class DefaultSupervisor:
    """The default supervisor implementation.

    Wires together: Planner, Capability Selector, Orchestrator, Reflection,
    Self-Correction, and QA.

    Usage:
        supervisor = DefaultSupervisor(
            registry=registry,
            orchestrator=orchestrator,
            router=router,
        )
        task_id = await supervisor.submit_goal('refactor auth module')
        result = await supervisor.wait_for_result(task_id)
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        orchestrator: TaskOrchestrator,
        router: ModelRouter | None = None,
        planner: LlmPlanner | None = None,
        reflection: DefaultReflectionAgent | None = None,
        correction: DefaultSelfCorrectionAgent | None = None,
        qa: DefaultQAAgent | None = None,
    ) -> None:
        self._registry = registry
        self._orchestrator = orchestrator
        self._router = router
        self._planner = planner or LlmPlanner(router=router)
        self._reflection = reflection or DefaultReflectionAgent(router=router)
        self._correction = correction or DefaultSelfCorrectionAgent(router=router)
        self._qa = qa or DefaultQAAgent(router=router)
        self._selector = CapabilitySelector(registry=registry)
        self._results: dict[UUID, TaskResult] = {}
        self._active_tasks: dict[UUID, Plan] = {}

    @property
    def selector(self) -> CapabilitySelector:
        """Return the capability selector."""
        return self._selector

    async def submit_goal(
        self,
        goal: str,
        *,
        context: TaskContext | None = None,
        priority: str = "normal",
    ) -> TaskId:
        """Submit a goal for execution.

        Returns the task ID. The goal will be decomposed into a plan and
        submitted to the orchestrator.
        """
        task_id = uuid4()

        # 1. Decompose the goal into a plan
        plan_result = await self._planner.decompose(goal, task_id)
        plan = plan_result.plan
        self._active_tasks[task_id] = plan

        _log.info(
            "supervisor.goal_submitted",
            task_id=str(task_id),
            goal=goal,
            step_count=len(plan.steps),
        )

        # 2. Set up the step executor (binds the supervisor to the orchestrator)
        async def step_executor(step: Step) -> dict[str, Any]:
            return await self._execute_step(task_id, step)

        # 3. Submit to the orchestrator
        self._orchestrator.set_step_executor(step_executor)
        await self._orchestrator.submit(plan, priority=priority)

        return task_id

    async def _execute_step(self, task_id: UUID, step: Step) -> dict[str, Any]:
        """Execute a single step: select agent → dispatch → reflect → correct → QA."""
        _log.info(
            "supervisor.executing_step",
            task_id=str(task_id),
            step_id=str(step.id),
            goal=step.goal,
            capability=step.capability,
        )

        # 1. Select an agent
        try:
            selection = self._selector.select(step.capability)
        except NoCandidateError as e:
            _log.error("supervisor.no_agent", capability=step.capability, error=str(e))
            raise

        agent = self._registry.get(selection.agent_id)
        # The registry returns an AgentProtocol; we need to call execute_task
        # which is part of the GenericAgent interface. Cast for mypy.
        from agents._types.gen import GenericAgent  # noqa: I001

        typed_agent: GenericAgent = agent  # type: ignore[assignment]
        step.assigned_agent_id = selection.agent_id

        # 2. Build a TaskRequest for the agent
        agent_request = TaskRequest(
            id=uuid4(),
            goal=step.goal,
            context=TaskContext(submitted_by=ActorRef.system()),
        )

        # 3. Execute the step (with retry + correction)
        max_correction = 3
        for attempt in range(max_correction):
            result = await typed_agent.execute_task(agent_request)

            if result.status == TaskResultStatus.SUCCESS:
                # 4. Reflection
                verdict, critique = await self._reflection.critique(
                    step_goal=step.goal,
                    agent_output=result.output,
                    success_criterion=step.success_criterion,
                )

                if verdict == ReflectionVerdict.ACCEPT:
                    # 5. QA
                    qa_verdict, qa_reason = await self._qa.validate(
                        deliverable=result.output,
                        success_criterion=step.success_criterion,
                    )
                    if qa_verdict == QAVerdict.PASS:
                        _log.info(
                            "supervisor.step_passed",
                            task_id=str(task_id),
                            step_id=str(step.id),
                            attempt=attempt + 1,
                        )
                        self._correction.reset_attempts(str(step.id))
                        return {
                            "output": result.output,
                            "agent_id": selection.agent_id,
                            "attempts": attempt + 1,
                            "qa_reason": qa_reason,
                        }
                    # QA failed — try correction
                    _log.warning(
                        "supervisor.qa_failed",
                        task_id=str(task_id),
                        step_id=str(step.id),
                        reason=qa_reason,
                    )
                elif verdict == ReflectionVerdict.NEEDS_CORRECTION:
                    # Try correction
                    _log.info(
                        "supervisor.needs_correction",
                        task_id=str(task_id),
                        step_id=str(step.id),
                        critique=critique,
                    )
                else:
                    # REJECT — try correction
                    _log.warning(
                        "supervisor.rejected",
                        task_id=str(task_id),
                        step_id=str(step.id),
                        critique=critique,
                    )

                # Attempt correction
                if self._correction.can_retry(str(step.id)):
                    corrected = await self._correction.correct(
                        step_goal=step.goal,
                        original_output=result.output,
                        critique=critique,
                        step_id=str(step.id),
                    )
                    # Use the corrected output for the next attempt
                    agent_request = TaskRequest(
                        id=uuid4(),
                        goal=f"{step.goal}\n\nCorrection feedback: {critique}\n\nCorrected approach: {corrected}",
                        context=TaskContext(submitted_by=ActorRef.system()),
                    )
                    continue
                else:
                    # Max corrections exceeded — fail the step
                    _log.error(
                        "supervisor.max_corrections",
                        task_id=str(task_id),
                        step_id=str(step.id),
                    )
                    raise RuntimeError(
                        f"Step {step.id} failed after {max_correction} correction attempts",
                    )
            else:
                # Agent returned failure
                _log.warning(
                    "supervisor.agent_failed",
                    task_id=str(task_id),
                    step_id=str(step.id),
                    error=result.error,
                )
                if attempt < max_correction - 1:
                    continue
                raise RuntimeError(f"Agent failed: {result.error}")

        # Should not reach here
        raise RuntimeError(f"Step {step.id} exhausted all attempts")

    async def get_result(self, task_id: TaskId) -> TaskResult | None:
        """Return the result of a completed task, or None if not done."""
        return self._results.get(task_id)

    def get_plan(self, task_id: TaskId) -> Plan | None:
        """Return the plan for a task, or None."""
        return self._active_tasks.get(task_id)

    def get_plan_status(self, task_id: TaskId) -> PlanStatus | None:
        """Return the plan status, or None."""
        plan = self._active_tasks.get(task_id)
        if plan is None:
            return None
        return plan.status
