"""Tests for the scheduler, workers, approval gates, and workflow engine."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest

from core.contracts.timestamp import utc_now
from orchestrator import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalGateManager,
    BackgroundJob,
    BackgroundJobStatus,
    BackgroundWorkerPool,
    GateType,
    Scheduler,
    ScheduleSpec,
    ScheduleType,
    Step,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowStore,
)


@pytest.mark.offline
class TestScheduler:
    """Scheduler tests."""

    async def test_one_time_schedule_fires(self) -> None:
        scheduler = Scheduler(check_interval_s=0.1)
        await scheduler.start()
        try:
            fired: list = []

            async def callback(task_id):  # type: ignore[no-untyped-def]
                fired.append(task_id)

            spec = ScheduleSpec(
                schedule_type=ScheduleType.ONE_TIME,
                run_at=utc_now() + timedelta(seconds=0.2),
            )
            task_id = await scheduler.schedule(spec, callback, name="test")
            # Wait for it to fire
            await asyncio.sleep(1.0)
            assert len(fired) == 1
            assert fired[0] == task_id
        finally:
            await scheduler.stop()

    async def test_interval_schedule_fires_multiple_times(self) -> None:
        scheduler = Scheduler(check_interval_s=0.1)
        await scheduler.start()
        try:
            fired: list = []

            async def callback(task_id):  # type: ignore[no-untyped-def]
                fired.append(task_id)

            spec = ScheduleSpec(
                schedule_type=ScheduleType.INTERVAL,
                interval_s=0.2,
                max_runs=3,
            )
            await scheduler.schedule(spec, callback, name="interval test")
            await asyncio.sleep(1.5)
            assert len(fired) == 3
        finally:
            await scheduler.stop()

    async def test_unschedule(self) -> None:
        scheduler = Scheduler()
        await scheduler.start()
        try:

            async def callback(task_id):  # type: ignore[no-untyped-def]
                pass

            spec = ScheduleSpec(
                schedule_type=ScheduleType.ONE_TIME,
                run_at=utc_now() + timedelta(hours=1),
            )
            task_id = await scheduler.schedule(spec, callback)
            assert scheduler.unschedule(task_id) is True
            assert scheduler.unschedule(task_id) is False  # already removed
        finally:
            await scheduler.stop()

    async def test_list_scheduled(self) -> None:
        scheduler = Scheduler()
        await scheduler.start()
        try:

            async def callback(task_id):  # type: ignore[no-untyped-def]
                pass

            spec = ScheduleSpec(
                schedule_type=ScheduleType.ONE_TIME,
                run_at=utc_now() + timedelta(hours=1),
            )
            await scheduler.schedule(spec, callback, name="one")
            await scheduler.schedule(spec, callback, name="two")
            tasks = scheduler.list_scheduled()
            assert len(tasks) == 2
        finally:
            await scheduler.stop()

    async def test_max_runs_stops_schedule(self) -> None:
        scheduler = Scheduler(check_interval_s=0.1)
        await scheduler.start()
        try:
            fired: list = []

            async def callback(task_id):  # type: ignore[no-untyped-def]
                fired.append(task_id)

            spec = ScheduleSpec(
                schedule_type=ScheduleType.INTERVAL,
                interval_s=0.1,
                max_runs=2,
            )
            task_id = await scheduler.schedule(spec, callback)
            await asyncio.sleep(1.0)
            assert len(fired) == 2
            # The task should be disabled
            task = scheduler.get(task_id)
            assert task is not None
            assert task.enabled is False
        finally:
            await scheduler.stop()


@pytest.mark.offline
class TestBackgroundWorkerPool:
    """BackgroundWorkerPool tests."""

    async def test_submit_and_get_result(self) -> None:
        pool = BackgroundWorkerPool(max_workers=2)
        await pool.start()
        try:

            async def work(job: BackgroundJob) -> str:
                return "done"

            job_id = await pool.submit(work, name="test job")
            # Wait for completion
            for _ in range(20):
                await asyncio.sleep(0.05)
                job = pool.get_job(job_id)
                if job and job.status in (
                    BackgroundJobStatus.SUCCEEDED,
                    BackgroundJobStatus.FAILED,
                ):
                    break
            job = pool.get_job(job_id)
            assert job is not None
            assert job.status == BackgroundJobStatus.SUCCEEDED
            assert job.result == "done"
        finally:
            await pool.stop()

    async def test_submit_with_failure(self) -> None:
        pool = BackgroundWorkerPool(max_workers=2)
        await pool.start()
        try:

            async def failing_work(job: BackgroundJob) -> None:
                raise RuntimeError("boom")

            job_id = await pool.submit(failing_work, name="failing job")
            for _ in range(20):
                await asyncio.sleep(0.05)
                job = pool.get_job(job_id)
                if job and job.status in (
                    BackgroundJobStatus.SUCCEEDED,
                    BackgroundJobStatus.FAILED,
                ):
                    break
            job = pool.get_job(job_id)
            assert job is not None
            assert job.status == BackgroundJobStatus.FAILED
            assert "boom" in (job.error or "")
        finally:
            await pool.stop()

    async def test_submit_with_timeout(self) -> None:
        pool = BackgroundWorkerPool(max_workers=2)
        await pool.start()
        try:

            async def slow_work(job: BackgroundJob) -> None:
                await asyncio.sleep(10)

            job_id = await pool.submit(slow_work, name="slow job", timeout_s=0.2)
            for _ in range(30):
                await asyncio.sleep(0.1)
                job = pool.get_job(job_id)
                if job and job.status in (
                    BackgroundJobStatus.SUCCEEDED,
                    BackgroundJobStatus.FAILED,
                ):
                    break
            job = pool.get_job(job_id)
            assert job is not None
            assert job.status == BackgroundJobStatus.FAILED
            assert "Timed out" in (job.error or "")
        finally:
            await pool.stop()

    async def test_list_jobs(self) -> None:
        pool = BackgroundWorkerPool(max_workers=4)
        await pool.start()
        try:

            async def work(job: BackgroundJob) -> None:
                pass

            await pool.submit(work, name="j1")
            await pool.submit(work, name="j2")
            jobs = pool.list_jobs()
            assert len(jobs) == 2
        finally:
            await pool.stop()


@pytest.mark.offline
class TestApprovalGateManager:
    """ApprovalGateManager tests."""

    async def test_request_and_approve(self) -> None:
        from core.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()
        manager = ApprovalGateManager(bus=bus)

        plan_id = uuid4()
        step = Step(goal="write file", capability="code.write")
        gate = ApprovalGate(gate_type=GateType.PRE_STEP, message="Approve write?", timeout_s=60)

        pending = await manager.request_approval(plan_id, step, gate)
        assert pending.id is not None
        assert manager.get_pending(pending.id) is not None

        # Approve
        result = await manager.respond(pending.id, ApprovalDecision.APPROVED)
        assert result is True
        # The future should be resolved
        decision = await pending.future
        assert decision == ApprovalDecision.APPROVED

    async def test_request_and_deny(self) -> None:
        from core.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()
        manager = ApprovalGateManager(bus=bus)

        plan_id = uuid4()
        step = Step(goal="delete file", capability="gateway.fs.delete")
        gate = ApprovalGate(gate_type=GateType.PRE_STEP, message="Approve delete?")

        pending = await manager.request_approval(plan_id, step, gate)
        result = await manager.respond(pending.id, ApprovalDecision.DENIED)
        assert result is True
        decision = await pending.future
        assert decision == ApprovalDecision.DENIED

    async def test_respond_unknown_returns_false(self) -> None:
        from core.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()
        manager = ApprovalGateManager(bus=bus)
        result = await manager.respond(uuid4(), ApprovalDecision.APPROVED)
        assert result is False

    async def test_list_pending(self) -> None:
        from core.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()
        manager = ApprovalGateManager(bus=bus)

        step = Step(goal="x", capability="code.write")
        gate = ApprovalGate(message="Approve?")
        await manager.request_approval(uuid4(), step, gate)
        await manager.request_approval(uuid4(), step, gate)
        pending = manager.list_pending()
        assert len(pending) == 2

    async def test_modified_decision_carries_inputs(self) -> None:
        from core.event_bus import InMemoryEventBus

        bus = InMemoryEventBus()
        manager = ApprovalGateManager(bus=bus)

        step = Step(goal="write file", capability="code.write")
        gate = ApprovalGate(message="Approve? Edit path if needed.")
        pending = await manager.request_approval(uuid4(), step, gate)
        modified = {"path": "/tmp/safe.txt"}
        await manager.respond(
            pending.id,
            ApprovalDecision.MODIFIED,
            modified_inputs=modified,
        )
        assert pending.modified_inputs == modified
        decision = await pending.future
        assert decision == ApprovalDecision.MODIFIED


@pytest.mark.offline
class TestWorkflowEngine:
    """WorkflowEngine tests."""

    async def test_save_and_get_workflow(self) -> None:
        store = WorkflowStore()
        engine = WorkflowEngine(store=store)
        wf = WorkflowDefinition(
            name="test workflow",
            step_templates=[
                {"name": "s1", "goal": "read", "capability": "code.read"},
                {
                    "name": "s2",
                    "goal": "write",
                    "capability": "code.write",
                    "depends_on_names": ["s1"],
                },
            ],
        )
        await engine.save(wf)
        fetched = await store.get(wf.id)
        assert fetched is not None
        assert fetched.name == "test workflow"
        assert len(fetched.step_templates) == 2

    async def test_instantiate_plan_resolves_dependencies(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDefinition(
            name="test",
            step_templates=[
                {"name": "s1", "goal": "read", "capability": "code.read"},
                {
                    "name": "s2",
                    "goal": "write",
                    "capability": "code.write",
                    "depends_on_names": ["s1"],
                },
            ],
        )
        plan = engine._instantiate_plan(wf, {}, uuid4())  # noqa: SLF001
        assert len(plan.steps) == 2
        # s2 depends on s1's UUID
        assert plan.steps[1].depends_on == [plan.steps[0].id]

    async def test_instantiate_plan_substitutes_variables(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDefinition(
            name="test",
            step_templates=[
                {
                    "name": "s1",
                    "goal": "read ${var.path}",
                    "capability": "code.read",
                    "inputs": {"path": "${var.path}"},
                },
            ],
            default_variables={"path": "/default/path"},
        )
        plan = engine._instantiate_plan(wf, {"path": "/custom/path"}, uuid4())  # noqa: SLF001
        assert plan.steps[0].inputs["path"] == "/custom/path"
        assert "/custom/path" in plan.steps[0].goal

    async def test_run_unknown_workflow_raises(self) -> None:
        engine = WorkflowEngine()
        with pytest.raises(ValueError, match="not found"):
            await engine.run(uuid4())

    async def test_list_workflows(self) -> None:
        store = WorkflowStore()
        engine = WorkflowEngine(store=store)
        await engine.save(WorkflowDefinition(name="wf1", step_templates=[]))
        await engine.save(WorkflowDefinition(name="wf2", step_templates=[]))
        workflows = await store.list()
        assert len(workflows) == 2

    async def test_delete_workflow(self) -> None:
        store = WorkflowStore()
        engine = WorkflowEngine(store=store)
        wf = WorkflowDefinition(name="test", step_templates=[])
        await engine.save(wf)
        assert await store.delete(wf.id) is True
        assert await store.delete(wf.id) is False  # already deleted
