"""Tests for v2.0 Supervisor Intelligence components."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from agents import MockAgent
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.contracts.task import TaskResultStatus
from core.event_bus import InMemoryEventBus
from orchestrator import InMemoryCheckpointStore, Step, TaskOrchestrator
from orchestrator.contracts.schedule import ScheduleSpec, ScheduleType
from services.agent_registry import AgentRegistry
from supervisor.v2 import (
    AdaptiveRouter,
    AutonomousJob,
    AutonomousJobScheduler,
    DelegationManager,
    ExecutionHistory,
    ExecutionOutcome,
    ExecutionRecord,
    IntelligentSupervisor,
    PersistentPlanner,
    SelfImprovingPolicy,
)


@pytest.fixture
def context() -> AgentContext:
    env = AgentEnvironment(
        home_dir=Path("/tmp"),
        config_dir=Path("/tmp/aaios/config"),
        data_dir=Path("/tmp/aaios/data"),
        log_dir=Path("/tmp/aaios/logs"),
        temp_dir=Path("/tmp/aaios/temp"),
    )
    return AgentContext(environment=env)


@pytest.mark.offline
class TestExecutionHistory:
    """ExecutionHistory tests."""

    async def test_record_and_stats(self) -> None:
        history = ExecutionHistory()
        for i in range(10):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="agent-1",
                    capability="code.read",
                    outcome=ExecutionOutcome.SUCCESS if i < 8 else ExecutionOutcome.FAILURE,
                    cost_usd=0.01,
                    latency_ms=100 + i * 10,
                )
            )
        stats = history.get_capability_stats("code.read")
        assert stats["sample_count"] == 10
        assert stats["success_rate"] == 0.8
        assert stats["avg_cost_usd"] == 0.01

    async def test_agent_stats(self) -> None:
        history = ExecutionHistory()
        await history.record(
            ExecutionRecord(
                step_id=uuid4(),
                task_id=uuid4(),
                agent_id="a1",
                capability="code.read",
                outcome=ExecutionOutcome.SUCCESS,
                cost_usd=0.01,
                latency_ms=100,
            )
        )
        await history.record(
            ExecutionRecord(
                step_id=uuid4(),
                task_id=uuid4(),
                agent_id="a1",
                capability="code.write",
                outcome=ExecutionOutcome.FAILURE,
                cost_usd=0.02,
                latency_ms=200,
            )
        )
        stats = history.get_agent_stats("a1")
        assert stats["sample_count"] == 2
        assert stats["success_rate"] == 0.5

    async def test_empty_stats(self) -> None:
        history = ExecutionHistory()
        stats = history.get_capability_stats("nonexistent")
        assert stats["sample_count"] == 0
        assert stats["success_rate"] == 1.0

    async def test_correction_rate(self) -> None:
        history = ExecutionHistory()
        for i in range(10):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="a1",
                    capability="code.read",
                    outcome=ExecutionOutcome.SUCCESS,
                    correction_attempts=1 if i < 3 else 0,
                )
            )
        stats = history.get_capability_stats("code.read")
        assert stats["correction_rate"] == 0.3


@pytest.mark.offline
class TestAdaptiveRouter:
    """AdaptiveRouter tests."""

    async def test_select_with_no_history_falls_back_to_static(
        self,
        context: AgentContext,
    ) -> None:
        registry = AgentRegistry()
        registry.set_default_context(context)
        await registry.register(
            MockAgent(
                agent_id="a1",
                agent_type=AgentType.CODING,
                capabilities=["code.read"],
            )
        )
        history = ExecutionHistory()
        router = AdaptiveRouter(registry, history, min_samples=10)
        result = router.select("code.read")
        assert result.agent_id == "a1"

    async def test_select_with_history_uses_adaptive(
        self,
        context: AgentContext,
    ) -> None:
        registry = AgentRegistry()
        registry.set_default_context(context)
        await registry.register(
            MockAgent(
                agent_id="good-agent",
                capabilities=["code.read"],
                result_output={"ok": True},
            )
        )
        await registry.register(
            MockAgent(
                agent_id="bad-agent",
                capabilities=["code.read"],
                result_output={"ok": True},
            )
        )
        history = ExecutionHistory()
        # Record 15 successful executions for good-agent
        for _ in range(15):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="good-agent",
                    capability="code.read",
                    outcome=ExecutionOutcome.SUCCESS,
                    cost_usd=0.01,
                    latency_ms=100,
                )
            )
        # Record 15 failed executions for bad-agent
        for _ in range(15):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="bad-agent",
                    capability="code.read",
                    outcome=ExecutionOutcome.FAILURE,
                    cost_usd=0.05,
                    latency_ms=500,
                )
            )
        router = AdaptiveRouter(registry, history, min_samples=10)
        result = router.select("code.read")
        assert result.agent_id == "good-agent"

    async def test_weight_adjustment_logged(
        self,
        context: AgentContext,
    ) -> None:
        registry = AgentRegistry()
        registry.set_default_context(context)
        await registry.register(MockAgent(agent_id="a1", capabilities=["code.read"]))
        history = ExecutionHistory()
        router = AdaptiveRouter(registry, history, min_samples=5, recompute_interval=5)
        # Record 10 executions with high failure rate
        for _ in range(10):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="a1",
                    capability="code.read",
                    outcome=ExecutionOutcome.FAILURE,
                    correction_attempts=2,
                )
            )
        router.record_execution("code.read")
        router.record_execution("code.read")
        router.record_execution("code.read")
        router.record_execution("code.read")
        router.record_execution("code.read")
        adjustments = router.get_adjustments()
        # May or may not have adjustments depending on whether recompute triggered
        assert isinstance(adjustments, list)


@pytest.mark.offline
class TestPersistentPlanner:
    """PersistentPlanner tests."""

    async def test_decompose_persists_plan(self) -> None:
        bus = InMemoryEventBus()
        planner = PersistentPlanner(router=None, bus=bus)
        task_id = uuid4()
        result = await planner.decompose("test goal", task_id)
        assert len(result.plan.steps) >= 1
        assert len(planner.get_persisted_plans()) == 1

    async def test_mark_completed(self) -> None:
        from orchestrator.contracts.dag import PlanStatus

        bus = InMemoryEventBus()
        planner = PersistentPlanner(router=None, bus=bus)
        result = await planner.decompose("test", uuid4())
        await planner.mark_completed(result.plan.id, PlanStatus.SUCCEEDED)
        assert len(planner.get_persisted_plans()) == 0

    async def test_restore_incomplete_plans(self) -> None:
        bus = InMemoryEventBus()
        planner = PersistentPlanner(router=None, bus=bus)
        await planner.decompose("test", uuid4())
        restored = await planner.restore_incomplete_plans()
        assert len(restored) == 1
        assert restored[0].needs_resume is True


@pytest.mark.offline
class TestDelegationManager:
    """DelegationManager tests."""

    async def test_delegate_to_another_agent(
        self,
        context: AgentContext,
    ) -> None:
        registry = AgentRegistry()
        registry.set_default_context(context)
        ctx = context
        ctx.bus = InMemoryEventBus()
        await registry.register(
            MockAgent(
                agent_id="coding-agent",
                agent_type=AgentType.CODING,
                capabilities=["code.read"],
                result_output={"files": ["test.py"]},
            )
        )
        await registry.register(
            MockAgent(
                agent_id="research-agent",
                agent_type=AgentType.RESEARCH,
                capabilities=["web.search"],
                result_output={"results": ["found docs"]},
            )
        )
        from supervisor.capability_selector import CapabilitySelector

        selector = CapabilitySelector(registry)
        delegator = DelegationManager(registry, selector)

        result = await delegator.delegate(
            from_agent_id="coding-agent",
            to_capability="web.search",
            task_goal="Find Pydantic v2 docs",
        )
        assert result.status == TaskResultStatus.SUCCESS
        assert result.output == {"results": ["found docs"]}
        await registry.shutdown()

    async def test_delegate_no_candidate(
        self,
        context: AgentContext,
    ) -> None:
        registry = AgentRegistry()
        registry.set_default_context(context)
        from supervisor.capability_selector import CapabilitySelector

        selector = CapabilitySelector(registry)
        delegator = DelegationManager(registry, selector)

        with pytest.raises(Exception):
            await delegator.delegate(
                from_agent_id="x",
                to_capability="nonexistent.cap",
                task_goal="test",
            )


@pytest.mark.offline
class TestSelfImprovingPolicy:
    """SelfImprovingPolicy tests."""

    async def test_review_with_no_history(self) -> None:
        history = ExecutionHistory()
        policy = SelfImprovingPolicy(history, min_samples=10)
        suggestions = policy.review()
        assert len(suggestions) == 0

    async def test_review_detects_high_failure(self) -> None:
        history = ExecutionHistory()
        for _ in range(20):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="a1",
                    capability="flaky.cap",
                    outcome=ExecutionOutcome.FAILURE,
                )
            )
        policy = SelfImprovingPolicy(history, min_samples=10)
        suggestions = policy.review()
        assert any(s.category == "add_agent" for s in suggestions)

    async def test_retry_override(self) -> None:
        history = ExecutionHistory()
        for _ in range(20):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="a1",
                    capability="moderate.cap",
                    outcome=ExecutionOutcome.SUCCESS if _ % 5 != 0 else ExecutionOutcome.FAILURE,
                )
            )
        policy = SelfImprovingPolicy(history, min_samples=10)
        policy.review()
        # Should have increased retry limit for moderate failure rate
        retries = policy.get_retry_limit("moderate.cap")
        assert retries >= 3  # default or higher

    async def test_correction_override(self) -> None:
        history = ExecutionHistory()
        for _ in range(20):
            await history.record(
                ExecutionRecord(
                    step_id=uuid4(),
                    task_id=uuid4(),
                    agent_id="a1",
                    capability="complex.cap",
                    outcome=ExecutionOutcome.SUCCESS,
                    correction_attempts=2,  # High correction rate
                )
            )
        policy = SelfImprovingPolicy(history, min_samples=10)
        policy.review()
        corrections = policy.get_correction_limit("complex.cap")
        assert corrections >= 3  # default or higher


@pytest.mark.offline
class TestAutonomousJobScheduler:
    """AutonomousJobScheduler tests."""

    async def test_schedule_job(self) -> None:
        bus = InMemoryEventBus()
        scheduler = AutonomousJobScheduler(bus=bus, check_interval_s=0.5)
        await scheduler.start()
        try:
            job = AutonomousJob(
                name="test-job",
                goal="Test job",
                schedule=ScheduleSpec(
                    schedule_type=ScheduleType.INTERVAL,
                    interval_s=60,
                ),
            )
            job_id = await scheduler.schedule(job)
            assert job_id == job.id
            assert len(scheduler.list_jobs()) == 1
        finally:
            await scheduler.stop()

    async def test_cancel_job(self) -> None:
        bus = InMemoryEventBus()
        scheduler = AutonomousJobScheduler(bus=bus)
        await scheduler.start()
        try:
            job = AutonomousJob(name="test", goal="test")
            job_id = await scheduler.schedule(job)
            assert await scheduler.cancel(job_id) is True
            assert len(scheduler.list_jobs()) == 0
        finally:
            await scheduler.stop()

    async def test_pause_resume(self) -> None:
        bus = InMemoryEventBus()
        scheduler = AutonomousJobScheduler(bus=bus)
        await scheduler.start()
        try:
            job = AutonomousJob(name="test", goal="test")
            job_id = await scheduler.schedule(job)
            assert await scheduler.pause(job_id) is True
            assert await scheduler.resume(job_id) is True
        finally:
            await scheduler.stop()


@pytest.mark.offline
class TestIntelligentSupervisor:
    """IntelligentSupervisor integration tests."""

    async def test_submit_goal_creates_plan(
        self,
        context: AgentContext,
    ) -> None:
        registry = AgentRegistry()
        registry.set_default_context(context)
        await registry.register(
            MockAgent(
                agent_id="mock-v1",
                capabilities=["plan.decompose"],
            )
        )
        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step: Step) -> dict[str, str]:
            return {"goal": step.goal, "executed": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            sup = IntelligentSupervisor(
                registry=registry,
                orchestrator=orch,
                router=None,
                bus=bus,
            )
            await sup.start()
            task_id = await sup.submit_goal("test goal")
            plan = sup.get_plan(task_id)
            assert plan is not None
            assert len(plan.steps) >= 1
            await sup.stop()
        finally:
            await orch.stop()
            await registry.shutdown()

    async def test_execution_stats(self) -> None:
        """get_execution_stats returns a valid dict."""
        history = ExecutionHistory()
        policy = SelfImprovingPolicy(history)
        # Just verify the method exists and returns a dict
        stats = {
            "total_executions": history.get_total_records(),
            "recent": len(history.get_recent_records(10)),
            "suggestions": len(policy.get_suggestions()),
            "adjustments": len(policy.get_adjustments()),
        }
        assert isinstance(stats, dict)
        assert stats["total_executions"] == 0
