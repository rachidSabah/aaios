"""Tests for the MockAgent and InProcessAgent base class."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents import MockAgent
from core.contracts.actor import ActorRef
from core.contracts.agent import (
    AgentContext,
    AgentEnvironment,
    AgentState,
    AgentType,
    StateIncompatibleError,
)
from core.contracts.health import HealthState
from core.contracts.task import (
    TaskContext,
    TaskProgressKind,
    TaskRequest,
    TaskResultStatus,
)


@pytest.fixture
def context() -> AgentContext:
    """A minimal AgentContext for tests."""
    env = AgentEnvironment(
        home_dir=Path("/tmp"),
        config_dir=Path("/tmp/aaios/config"),
        data_dir=Path("/tmp/aaios/data"),
        log_dir=Path("/tmp/aaios/logs"),
        temp_dir=Path("/tmp/aaios/temp"),
    )
    return AgentContext(environment=env)


def _make_request(goal: str = "test") -> TaskRequest:
    """Build a minimal TaskRequest."""
    return TaskRequest(
        goal=goal,
        context=TaskContext(submitted_by=ActorRef.user("alice")),
    )


@pytest.mark.offline
class TestMockAgentLifecycle:
    """MockAgent lifecycle tests."""

    async def test_initialize_and_shutdown(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        assert not agent._initialized  # noqa: SLF001
        await agent.initialize(context)
        assert agent._initialized  # noqa: SLF001
        await agent.shutdown()
        assert not agent._initialized  # noqa: SLF001

    async def test_initialize_is_idempotent(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        await agent.initialize(context)
        await agent.initialize(context)  # no-op
        assert agent._initialized  # noqa: SLF001

    async def test_shutdown_is_idempotent(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        await agent.initialize(context)
        await agent.shutdown()
        await agent.shutdown()  # no-op, no raise

    async def test_initialize_failure(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="broken-v1",
            capabilities=["x"],
            fail_initialize=True,
        )
        with pytest.raises(RuntimeError, match="configured to fail"):
            await agent.initialize(context)


@pytest.mark.offline
class TestMockAgentCapabilities:
    """MockAgent capability discovery tests."""

    async def test_discover_capabilities(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            agent_type=AgentType.CODING,
            capabilities=["code.read", "code.write"],
        )
        await agent.initialize(context)
        manifest = await agent.discover_capabilities()
        assert manifest.identity.agent_id == "test-v1"
        assert manifest.identity.agent_type == AgentType.CODING
        assert manifest.has_capability("code.read")
        assert manifest.has_capability("code.write")
        assert not manifest.has_capability("code.refactor")

    async def test_discover_capabilities_before_init_raises(self) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        with pytest.raises(RuntimeError, match="not initialized"):
            await agent.discover_capabilities()


@pytest.mark.offline
class TestMockAgentExecution:
    """MockAgent execute_task + stream_progress tests."""

    async def test_execute_task_returns_configured_result(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            result_status=TaskResultStatus.SUCCESS,
            result_output={"files": ["auth.py"]},
        )
        await agent.initialize(context)
        request = _make_request("refactor auth")
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.SUCCESS
        assert result.output == {"files": ["auth.py"]}

    async def test_execute_task_records_call(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        await agent.initialize(context)
        request = _make_request("do thing")
        await agent.execute_task(request)
        assert len(agent.execute_calls) == 1
        assert agent.execute_calls[0].goal == "do thing"

    async def test_execute_task_increments_completed(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            result_status=TaskResultStatus.SUCCESS,
        )
        await agent.initialize(context)
        await agent.execute_task(_make_request())
        await agent.execute_task(_make_request())
        metrics = await agent.report_metrics()
        assert metrics.tasks_completed == 2

    async def test_execute_task_failure_increments_failed(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            result_status=TaskResultStatus.FAILURE,
            result_error="mock failure",
        )
        await agent.initialize(context)
        result = await agent.execute_task(_make_request())
        assert result.status == TaskResultStatus.FAILURE
        assert result.error == "mock failure"
        metrics = await agent.report_metrics()
        assert metrics.tasks_failed == 1

    async def test_execute_task_before_init_raises(self) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        with pytest.raises(RuntimeError, match="not initialized"):
            await agent.execute_task(_make_request())

    async def test_stream_progress_yields_started_then_result(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            result_status=TaskResultStatus.SUCCESS,
        )
        await agent.initialize(context)
        request = _make_request()
        events = []
        async for progress in agent.stream_progress(request):
            events.append(progress)
        assert len(events) == 2
        assert events[0].kind == TaskProgressKind.STARTED
        assert events[1].kind == TaskProgressKind.RESULT
        assert events[1].result is not None
        assert events[1].result.status == TaskResultStatus.SUCCESS


@pytest.mark.offline
class TestMockAgentHealth:
    """MockAgent report_health tests."""

    async def test_healthy_by_default(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            initial_health=HealthState.HEALTHY,
        )
        await agent.initialize(context)
        health = await agent.report_health()
        assert health.state == HealthState.HEALTHY

    async def test_degraded(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            initial_health=HealthState.DEGRADED,
        )
        await agent.initialize(context)
        health = await agent.report_health()
        assert health.state == HealthState.DEGRADED

    async def test_unhealthy_before_init(self) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        health = await agent.report_health()
        assert health.state == HealthState.UNHEALTHY


@pytest.mark.offline
class TestMockAgentState:
    """MockAgent serialize_state / restore_state tests."""

    async def test_serialize_state_includes_metrics(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        await agent.initialize(context)
        await agent.execute_task(_make_request())
        state = await agent.serialize_state()
        assert state.agent_id == "test-v1"
        assert state.format == "mock-1"
        assert state.data["execute_calls_count"] == 1
        assert state.data["tasks_completed"] == 1

    async def test_restore_state_with_matching_format(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        await agent.initialize(context)
        state = AgentState(agent_id="test-v1", format="mock-1", data={"execute_calls_count": 5})
        # Should not raise
        await agent.restore_state(state)

    async def test_restore_state_with_incompatible_format(self, context: AgentContext) -> None:
        agent = MockAgent(agent_id="test-v1", capabilities=["x"])
        await agent.initialize(context)
        state = AgentState(agent_id="test-v1", format="incompatible", data={})
        with pytest.raises(StateIncompatibleError):
            await agent.restore_state(state)


@pytest.mark.offline
class TestMockAgentMetrics:
    """MockAgent report_metrics tests."""

    async def test_metrics_after_multiple_tasks(self, context: AgentContext) -> None:
        agent = MockAgent(
            agent_id="test-v1",
            capabilities=["x"],
            result_status=TaskResultStatus.SUCCESS,
        )
        await agent.initialize(context)
        for _ in range(5):
            await agent.execute_task(_make_request())
        metrics = await agent.report_metrics()
        assert metrics.tasks_completed == 5
        assert metrics.tasks_failed == 0
        assert metrics.success_rate == 1.0
        assert metrics.avg_latency_ms >= 0.0
