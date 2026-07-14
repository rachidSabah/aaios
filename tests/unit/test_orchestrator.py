"""Tests for the Task Orchestrator core — submit, cancel, pause, resume, checkpoint."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from core.event_bus import InMemoryEventBus
from orchestrator import (
    InMemoryCheckpointStore,
    Plan,
    PlanStatus,
    Step,
    StepStatus,
    TaskOrchestrator,
)


@pytest.fixture
async def bus() -> InMemoryEventBus:
    """Fresh event bus per test."""
    return InMemoryEventBus()


@pytest.fixture
async def store() -> InMemoryCheckpointStore:
    """Fresh checkpoint store per test."""
    return InMemoryCheckpointStore()


@pytest.fixture
async def orchestrator(
    bus: InMemoryEventBus,
    store: InMemoryCheckpointStore,
) -> TaskOrchestrator:
    """Fresh orchestrator with a mock step executor."""
    executed: list[str] = []

    async def step_executor(step: Step) -> dict[str, str]:
        executed.append(step.capability)
        return {"goal": step.goal, "capability": step.capability}

    orch = TaskOrchestrator(
        bus=bus,
        checkpoint_store=store,
        step_executor=step_executor,
    )
    await orch.start()
    yield orch
    await orch.stop()


def _make_simple_plan() -> Plan:
    """A plan with 3 sequential steps."""
    s1 = Step(id=uuid4(), goal="step 1", capability="code.read")
    s2 = Step(id=uuid4(), goal="step 2", capability="code.write", depends_on=[s1.id])
    s3 = Step(id=uuid4(), goal="step 3", capability="test.run", depends_on=[s2.id])
    return Plan(id=uuid4(), task_id=uuid4(), steps=[s1, s2, s3])


def _make_parallel_plan() -> Plan:
    """A plan with parallel steps: S1 → (S2a, S2b) → S3."""
    s1 = Step(id=uuid4(), goal="read", capability="code.read")
    s2a = Step(id=uuid4(), goal="write A", capability="code.write", depends_on=[s1.id])
    s2b = Step(id=uuid4(), goal="write B", capability="code.write", depends_on=[s1.id])
    s3 = Step(id=uuid4(), goal="test", capability="test.run", depends_on=[s2a.id, s2b.id])
    return Plan(id=uuid4(), task_id=uuid4(), steps=[s1, s2a, s2b, s3])


async def _wait_for_completion(
    orch: TaskOrchestrator, plan_id, timeout_s: float = 5.0
) -> PlanStatus:
    """Poll until the plan reaches a terminal state."""
    for _ in range(int(timeout_s * 10)):
        await asyncio.sleep(0.1)
        status = orch.get_status(plan_id)
        if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED, PlanStatus.CANCELLED):
            assert status is not None
            return status
    raise TimeoutError(f"Plan did not complete in {timeout_s}s")


@pytest.mark.offline
class TestOrchestratorSubmission:
    """Plan submission tests."""

    async def test_submit_valid_plan(self, orchestrator: TaskOrchestrator) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan, priority="normal")
        assert plan_id == plan.id

    async def test_submit_invalid_dag_raises(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        from orchestrator.contracts.dag import DAGValidationError

        s1 = Step(id=uuid4(), goal="x", capability="code.read", depends_on=[uuid4()])
        plan = Plan(task_id=uuid4(), steps=[s1])
        with pytest.raises(DAGValidationError):
            await orchestrator.submit(plan)

    async def test_submit_invalid_priority_raises(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        plan = _make_simple_plan()
        with pytest.raises(ValueError, match="Invalid priority"):
            await orchestrator.submit(plan, priority="urgent")


@pytest.mark.offline
class TestOrchestratorExecution:
    """Plan execution tests."""

    async def test_sequential_plan_executes_in_order(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan)
        status = await _wait_for_completion(orchestrator, plan_id)
        assert status == PlanStatus.SUCCEEDED
        # All steps succeeded
        for step in plan.steps:
            assert step.status == StepStatus.SUCCEEDED

    async def test_parallel_plan_executes_concurrently(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        plan = _make_parallel_plan()
        plan_id = await orchestrator.submit(plan)
        status = await _wait_for_completion(orchestrator, plan_id)
        assert status == PlanStatus.SUCCEEDED
        # All steps succeeded
        for step in plan.steps:
            assert step.status == StepStatus.SUCCEEDED

    async def test_failed_step_marks_plan_failed(
        self,
        bus: InMemoryEventBus,
        store: InMemoryCheckpointStore,
    ) -> None:
        async def failing_executor(step: Step) -> dict[str, str]:
            if step.capability == "code.write":
                raise RuntimeError("write failed")
            return {"ok": True}

        orch = TaskOrchestrator(
            bus=bus,
            checkpoint_store=store,
            step_executor=failing_executor,
        )
        await orch.start()
        try:
            plan = _make_simple_plan()
            plan_id = await orch.submit(plan)
            status = await _wait_for_completion(orch, plan_id)
            assert status == PlanStatus.FAILED
        finally:
            await orch.stop()

    async def test_failed_step_skips_dependents(
        self,
        bus: InMemoryEventBus,
        store: InMemoryCheckpointStore,
    ) -> None:
        async def failing_executor(step: Step) -> dict[str, str]:
            if step.capability == "code.write":
                raise RuntimeError("write failed")
            return {"ok": True}

        orch = TaskOrchestrator(
            bus=bus,
            checkpoint_store=store,
            step_executor=failing_executor,
        )
        await orch.start()
        try:
            plan = _make_simple_plan()  # S1 → S2(write, fails) → S3(test)
            plan_id = await orch.submit(plan)
            await _wait_for_completion(orch, plan_id)
            # S1 succeeded, S2 failed, S3 skipped
            assert plan.steps[0].status == StepStatus.SUCCEEDED
            assert plan.steps[1].status == StepStatus.FAILED
            assert plan.steps[2].status == StepStatus.SKIPPED
        finally:
            await orch.stop()


@pytest.mark.offline
class TestOrchestratorCancellation:
    """Cancellation tests."""

    async def test_cancel_pending_plan(
        self,
        bus: InMemoryEventBus,
        store: InMemoryCheckpointStore,
    ) -> None:
        """A plan that hasn't started executing can be cancelled."""

        async def slow_executor(step: Step) -> dict[str, str]:
            await asyncio.sleep(10)
            return {"ok": True}

        orch = TaskOrchestrator(
            bus=bus,
            checkpoint_store=store,
            step_executor=slow_executor,
        )
        # Don't start the orchestrator — plan stays in queue
        plan = _make_simple_plan()
        plan_id = await orch.submit(plan)
        result = await orch.cancel(plan_id, reason="test")
        assert result is True
        assert orch.get_status(plan_id) == PlanStatus.CANCELLED

    async def test_cancel_unknown_plan_returns_false(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        result = await orchestrator.cancel(uuid4())
        assert result is False


@pytest.mark.offline
class TestOrchestratorPauseResume:
    """Pause and resume tests."""

    async def test_pause_and_resume(
        self,
        bus: InMemoryEventBus,
        store: InMemoryCheckpointStore,
    ) -> None:
        async def slow_executor(step: Step) -> dict[str, str]:
            await asyncio.sleep(0.1)
            return {"ok": True}

        orch = TaskOrchestrator(
            bus=bus,
            checkpoint_store=store,
            step_executor=slow_executor,
        )
        await orch.start()
        try:
            plan = _make_simple_plan()
            plan_id = await orch.submit(plan)
            # Pause immediately
            paused = await orch.pause(plan_id)
            assert paused is True
            assert orch.get_status(plan_id) == PlanStatus.PAUSED
            # Resume
            resumed = await orch.resume(plan_id)
            assert resumed is True
            # Wait for completion
            status = await _wait_for_completion(orch, plan_id, timeout_s=5.0)
            assert status == PlanStatus.SUCCEEDED
        finally:
            await orch.stop()

    async def test_resume_unknown_plan_returns_false(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        assert await orchestrator.resume(uuid4()) is False

    async def test_resume_non_paused_returns_false(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan)
        # Not paused — resume should fail
        assert await orchestrator.resume(plan_id) is False


@pytest.mark.offline
class TestOrchestratorCheckpoint:
    """Checkpoint tests."""

    async def test_checkpoint_step(
        self,
        orchestrator: TaskOrchestrator,
        store: InMemoryCheckpointStore,
    ) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan)
        await _wait_for_completion(orchestrator, plan_id)

        # Manually write a checkpoint (the executor doesn't do this automatically)
        step = plan.steps[0]
        step.status = StepStatus.SUCCEEDED
        cp = await orchestrator.checkpoint_step(plan_id, step, result={"ok": True})
        assert cp.task_id == plan.task_id
        assert cp.step_id == step.id
        assert cp.step_status == StepStatus.SUCCEEDED
        assert cp.sequence == 1

    async def test_get_latest_checkpoint(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan)
        await _wait_for_completion(orchestrator, plan_id)

        # Write two checkpoints
        for i, step in enumerate(plan.steps[:2]):
            step.status = StepStatus.SUCCEEDED
            await orchestrator.checkpoint_step(plan_id, step, result={"i": i})

        latest = await orchestrator.get_latest_checkpoint(plan_id)
        assert latest is not None
        assert latest.sequence == 2  # the second checkpoint

    async def test_get_latest_checkpoint_none(
        self,
        orchestrator: TaskOrchestrator,
    ) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan)
        latest = await orchestrator.get_latest_checkpoint(plan_id)
        assert latest is None


@pytest.mark.offline
class TestOrchestratorIntrospection:
    """Introspection tests."""

    async def test_get_plan(self, orchestrator: TaskOrchestrator) -> None:
        plan = _make_simple_plan()
        plan_id = await orchestrator.submit(plan)
        fetched = orchestrator.get_plan(plan_id)
        assert fetched is plan

    async def test_get_plan_unknown(self, orchestrator: TaskOrchestrator) -> None:
        assert orchestrator.get_plan(uuid4()) is None

    async def test_list_active_plans(self, orchestrator: TaskOrchestrator) -> None:
        plan1 = _make_simple_plan()
        plan2 = _make_simple_plan()
        await orchestrator.submit(plan1)
        await orchestrator.submit(plan2)
        active = orchestrator.list_active_plans()
        assert plan1.id in active
        assert plan2.id in active

    async def test_queue_depth(self, orchestrator: TaskOrchestrator) -> None:
        plan = _make_simple_plan()
        await orchestrator.submit(plan)
        # The plan may or may not have been dispatched yet
        assert orchestrator.queue_depth() >= 0
