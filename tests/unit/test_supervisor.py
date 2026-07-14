"""Tests for the Supervisor — capability selector, planner, reflection, QA."""

from __future__ import annotations

from uuid import uuid4

import pytest

from agents import MockAgent
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from services.agent_registry import AgentRegistry
from supervisor import (
    CapabilitySelector,
    DefaultQAAgent,
    DefaultReflectionAgent,
    DefaultSelfCorrectionAgent,
    DefaultSupervisor,
    LlmPlanner,
    NoCandidateError,
    QAVerdict,
    ReflectionVerdict,
)


@pytest.fixture
async def registry() -> AgentRegistry:
    """Fresh registry with a default context."""
    reg = AgentRegistry()
    env = AgentEnvironment(
        home_dir=__import__("pathlib").Path("/tmp"),
        config_dir=__import__("pathlib").Path("/tmp/aaios/config"),
        data_dir=__import__("pathlib").Path("/tmp/aaios/data"),
        log_dir=__import__("pathlib").Path("/tmp/aaios/logs"),
        temp_dir=__import__("pathlib").Path("/tmp/aaios/temp"),
    )
    reg.set_default_context(AgentContext(environment=env))
    yield reg
    await reg.shutdown()


@pytest.mark.offline
class TestCapabilitySelector:
    """CapabilitySelector tests."""

    async def test_select_single_candidate(self, registry: AgentRegistry) -> None:
        await registry.register(
            MockAgent(
                agent_id="a1",
                agent_type=AgentType.CODING,
                capabilities=["code.read"],
            )
        )
        selector = CapabilitySelector(registry)
        result = selector.select("code.read")
        assert result.agent_id == "a1"
        assert result.score == 1.0

    async def test_select_no_candidate_raises(self, registry: AgentRegistry) -> None:
        selector = CapabilitySelector(registry)
        with pytest.raises(NoCandidateError):
            selector.select("nonexistent.capability")

    async def test_select_multiple_candidates(self, registry: AgentRegistry) -> None:
        await registry.register(
            MockAgent(
                agent_id="a1",
                capabilities=["code.read"],
            )
        )
        await registry.register(
            MockAgent(
                agent_id="a2",
                capabilities=["code.read"],
            )
        )
        selector = CapabilitySelector(registry)
        result = selector.select("code.read")
        assert result.agent_id in ("a1", "a2")
        assert len(result.candidates) == 2

    async def test_pin_agent(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["code.read"]))
        await registry.register(MockAgent(agent_id="a2", capabilities=["code.read"]))
        selector = CapabilitySelector(registry)
        selector.pin_agent("code.read", "a2")
        result = selector.select("code.read")
        assert result.agent_id == "a2"

    async def test_unpin(self, registry: AgentRegistry) -> None:
        selector = CapabilitySelector(registry)
        selector.pin_agent("code.read", "a1")
        assert selector.unpin("code.read") is True
        assert selector.unpin("code.read") is False

    async def test_skips_unhealthy(self, registry: AgentRegistry) -> None:
        from core.contracts.health import HealthState

        await registry.register(
            MockAgent(
                agent_id="healthy",
                capabilities=["code.read"],
                initial_health=HealthState.HEALTHY,
            )
        )
        await registry.register(
            MockAgent(
                agent_id="unhealthy",
                capabilities=["code.read"],
                initial_health=HealthState.UNHEALTHY,
            )
        )
        selector = CapabilitySelector(registry)
        result = selector.select("code.read")
        assert result.agent_id == "healthy"


@pytest.mark.offline
class TestLlmPlanner:
    """LlmPlanner tests."""

    async def test_fallback_plan_no_router(self) -> None:
        """Without a router, the planner creates a single-step fallback plan."""
        planner = LlmPlanner(router=None)
        task_id = uuid4()
        result = await planner.decompose("do something", task_id)
        assert len(result.plan.steps) == 1
        assert result.plan.steps[0].goal == "do something"
        assert result.plan.steps[0].capability == "plan.decompose"
        assert result.plan.task_id == task_id


@pytest.mark.offline
class TestReflectionAgent:
    """DefaultReflectionAgent tests."""

    async def test_no_router_auto_accepts(self) -> None:
        agent = DefaultReflectionAgent(router=None)
        verdict, critique = await agent.critique("do thing", {"result": "ok"})
        assert verdict == ReflectionVerdict.ACCEPT
        assert "auto-accepted" in critique.lower()


@pytest.mark.offline
class TestSelfCorrectionAgent:
    """DefaultSelfCorrectionAgent tests."""

    async def test_no_router_returns_original(self) -> None:
        agent = DefaultSelfCorrectionAgent(router=None)
        result = await agent.correct("do thing", "original output", "bad critique")
        assert result == "original output"

    def test_can_retry(self) -> None:
        agent = DefaultSelfCorrectionAgent(router=None)
        assert agent.can_retry("step-1") is True

    def test_reset_attempts(self) -> None:
        agent = DefaultSelfCorrectionAgent(router=None)
        agent._attempts["step-1"] = 2  # noqa: SLF001
        agent.reset_attempts("step-1")
        assert agent.can_retry("step-1") is True


@pytest.mark.offline
class TestQAAgent:
    """DefaultQAAgent tests."""

    async def test_no_criterion_auto_passes(self) -> None:
        agent = DefaultQAAgent(router=None)
        verdict, reason = await agent.validate("deliverable", "")
        assert verdict == QAVerdict.PASS
        assert "auto-passed" in reason.lower()

    async def test_no_router_auto_passes(self) -> None:
        agent = DefaultQAAgent(router=None)
        verdict, reason = await agent.validate("deliverable", "must be correct")
        assert verdict == QAVerdict.PASS
        assert "auto-passed" in reason.lower()


@pytest.mark.offline
class TestDefaultSupervisor:
    """DefaultSupervisor tests (with mock agents, no real LLM)."""

    async def test_submit_goal_creates_plan(self, registry: AgentRegistry) -> None:
        """Submitting a goal creates a plan (fallback single-step since no router)."""
        from core.event_bus import InMemoryEventBus
        from orchestrator import InMemoryCheckpointStore, TaskOrchestrator

        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step):  # type: ignore[no-untyped-def]
            return {"output": "done"}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()

        try:
            supervisor = DefaultSupervisor(
                registry=registry,
                orchestrator=orch,
                router=None,
            )
            task_id = await supervisor.submit_goal("test goal")
            assert task_id is not None
            plan = supervisor.get_plan(task_id)
            assert plan is not None
            assert len(plan.steps) >= 1
        finally:
            await orch.stop()
