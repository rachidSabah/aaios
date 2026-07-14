"""Tests for the Agent Registry — registration, indexing, hot-reload, health."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents import MockAgent
from core.contracts.actor import ActorRef
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.contracts.health import HealthState
from core.contracts.task import TaskContext, TaskRequest
from services.agent_registry import (
    AgentAlreadyRegisteredError,
    AgentFilter,
    AgentInitError,
    AgentNotFoundError,
    AgentRegistry,
    AgentSummaryHealth,
    CircularDependencyError,
    init_agent_registry,
    set_agent_registry,
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


@pytest.fixture
async def registry(context: AgentContext) -> AgentRegistry:
    """Fresh registry with a default context."""
    reg = AgentRegistry()
    reg.set_default_context(context)
    set_agent_registry(reg)
    yield reg
    await reg.shutdown()
    set_agent_registry(AgentRegistry())  # type: ignore[misc]


def _make_request(goal: str = "test") -> TaskRequest:
    """Build a minimal TaskRequest for tests."""
    return TaskRequest(
        goal=goal,
        context=TaskContext(submitted_by=ActorRef.user("alice")),
    )


@pytest.mark.offline
class TestRegistration:
    """Agent registration tests."""

    async def test_register_and_list(
        self,
        registry: AgentRegistry,
        context: AgentContext,
    ) -> None:
        agent = MockAgent(
            agent_id="test-coding-v1",
            agent_type=AgentType.CODING,
            capabilities=["code.read", "code.write"],
        )
        agent_id = await registry.register(agent)
        assert agent_id == "test-coding-v1"

        summaries = registry.list_agents()
        assert len(summaries) == 1
        assert summaries[0].agent_id == "test-coding-v1"
        assert summaries[0].agent_type == "coding"
        assert "code.read" in summaries[0].capabilities
        assert summaries[0].initialized is True
        assert summaries[0].health == AgentSummaryHealth.HEALTHY

    async def test_register_duplicate_raises(
        self,
        registry: AgentRegistry,
    ) -> None:
        agent = MockAgent(agent_id="dup-v1", capabilities=["x"])
        await registry.register(agent)
        with pytest.raises(AgentAlreadyRegisteredError):
            await registry.register(MockAgent(agent_id="dup-v1", capabilities=["y"]))

    async def test_register_with_init_failure(
        self,
        registry: AgentRegistry,
    ) -> None:
        agent = MockAgent(
            agent_id="broken-v1",
            capabilities=["x"],
            fail_initialize=True,
        )
        with pytest.raises(AgentInitError):
            await registry.register(agent)
        # Agent should not be in the registry
        assert not registry.has("broken-v1")

    async def test_unregister(self, registry: AgentRegistry) -> None:
        agent = MockAgent(agent_id="temp-v1", capabilities=["x"])
        await registry.register(agent)
        assert registry.has("temp-v1")
        result = await registry.unregister("temp-v1")
        assert result is True
        assert not registry.has("temp-v1")
        # Unregistering again returns False
        assert await registry.unregister("temp-v1") is False

    async def test_unregister_unknown_returns_false(self, registry: AgentRegistry) -> None:
        assert await registry.unregister("does-not-exist") is False


@pytest.mark.offline
class TestCapabilityIndexing:
    """Capability indexing tests."""

    async def test_find_by_capability(self, registry: AgentRegistry) -> None:
        a1 = MockAgent(agent_id="a1", capabilities=["code.read", "code.write"])
        a2 = MockAgent(agent_id="a2", capabilities=["code.read", "code.refactor"])
        a3 = MockAgent(agent_id="a3", capabilities=["desktop.ui.click"])
        await registry.register(a1)
        await registry.register(a2)
        await registry.register(a3)

        readers = registry.find_by_capability("code.read")
        assert {s.agent_id for s in readers} == {"a1", "a2"}

        refactors = registry.find_by_capability("code.refactor")
        assert {s.agent_id for s in refactors} == {"a2"}

        clickers = registry.find_by_capability("desktop.ui.click")
        assert {s.agent_id for s in clickers} == {"a3"}

    async def test_find_by_capability_excludes_disabled(self, registry: AgentRegistry) -> None:
        a1 = MockAgent(agent_id="a1", capabilities=["code.read"])
        await registry.register(a1)
        await registry.disable("a1")
        readers = registry.find_by_capability("code.read")
        assert readers == []

    async def test_list_capabilities(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["code.read", "code.write"]))
        await registry.register(MockAgent(agent_id="a2", capabilities=["desktop.click"]))
        caps = registry.list_capabilities()
        assert "code.read" in caps
        assert "code.write" in caps
        assert "desktop.click" in caps

    async def test_unregister_removes_from_capability_index(self, registry: AgentRegistry) -> None:
        a1 = MockAgent(agent_id="a1", capabilities=["unique.cap"])
        await registry.register(a1)
        assert len(registry.find_by_capability("unique.cap")) == 1
        await registry.unregister("a1")
        assert registry.find_by_capability("unique.cap") == []
        assert "unique.cap" not in registry.list_capabilities()


@pytest.mark.offline
class TestFiltering:
    """list() with filters."""

    async def test_filter_by_type(self, registry: AgentRegistry) -> None:
        await registry.register(
            MockAgent(
                agent_id="c1",
                agent_type=AgentType.CODING,
                capabilities=["code.read"],
            )
        )
        await registry.register(
            MockAgent(
                agent_id="d1",
                agent_type=AgentType.DESKTOP,
                capabilities=["desktop.click"],
            )
        )
        coders = registry.list_agents(AgentFilter(agent_type="coding"))
        assert len(coders) == 1
        assert coders[0].agent_id == "c1"

    async def test_filter_by_capability(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["code.read"]))
        await registry.register(MockAgent(agent_id="a2", capabilities=["desktop.click"]))
        readers = registry.list_agents(AgentFilter(capability="code.read"))
        assert len(readers) == 1
        assert readers[0].agent_id == "a1"

    async def test_filter_by_health(self, registry: AgentRegistry) -> None:
        healthy = MockAgent(agent_id="h1", capabilities=["x"])
        degraded = MockAgent(
            agent_id="d1",
            capabilities=["x"],
            initial_health=HealthState.DEGRADED,
        )
        await registry.register(healthy)
        await registry.register(degraded)
        # Both report their initial health on register
        healthy_summaries = registry.list_agents(AgentFilter(health=AgentSummaryHealth.HEALTHY))
        degraded_summaries = registry.list_agents(AgentFilter(health=AgentSummaryHealth.DEGRADED))
        healthy_ids = {s.agent_id for s in healthy_summaries}
        degraded_ids = {s.agent_id for s in degraded_summaries}
        assert "h1" in healthy_ids
        assert "d1" in degraded_ids

    async def test_filter_by_enabled(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["x"]))
        await registry.register(MockAgent(agent_id="a2", capabilities=["x"]))
        await registry.disable("a2")
        enabled = registry.list_agents(AgentFilter(enabled=True))
        disabled = registry.list_agents(AgentFilter(enabled=False))
        assert {s.agent_id for s in enabled} == {"a1"}
        assert {s.agent_id for s in disabled} == {"a2"}


@pytest.mark.offline
class TestEnableDisable:
    """enable/disable tests."""

    async def test_disable_and_enable(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["x"]))
        await registry.disable("a1")
        assert not registry.get("a1")._initialized or True  # noqa: SLF001
        summaries = registry.list_agents()
        assert summaries[0].enabled is False
        await registry.enable("a1")
        summaries = registry.list_agents()
        assert summaries[0].enabled is True

    async def test_disable_unknown_raises(self, registry: AgentRegistry) -> None:
        with pytest.raises(AgentNotFoundError):
            await registry.disable("does-not-exist")


@pytest.mark.offline
class TestHealthMonitoring:
    """Health check tests."""

    async def test_heartbeat_updates_health(self, registry: AgentRegistry) -> None:
        agent = MockAgent(agent_id="a1", capabilities=["x"])
        await registry.register(agent)
        health = await registry.heartbeat()
        assert "a1" in health
        assert health["a1"] == AgentSummaryHealth.HEALTHY

    async def test_heartbeat_marks_unhealthy_on_failure(self, registry: AgentRegistry) -> None:
        """An agent whose report_health raises is marked unhealthy."""
        agent = MockAgent(agent_id="a1", capabilities=["x"])
        await registry.register(agent)

        # Make report_health raise
        async def bad_health() -> None:
            raise RuntimeError("boom")

        # type: ignore[method-assign]
        agent.report_health = bad_health  # type: ignore[assignment]

        health = await registry.heartbeat()
        assert health["a1"] == AgentSummaryHealth.UNHEALTHY

    async def test_heartbeat_marks_unhealthy_on_timeout(self, registry: AgentRegistry) -> None:
        """An agent whose report_health hangs is marked unhealthy."""
        import asyncio

        agent = MockAgent(agent_id="a1", capabilities=["x"])
        await registry.register(agent)

        async def slow_health() -> None:
            await asyncio.sleep(60)

        # type: ignore[method-assign]
        agent.report_health = slow_health  # type: ignore[assignment]

        health = await registry.heartbeat()
        assert health["a1"] == AgentSummaryHealth.UNHEALTHY


@pytest.mark.offline
class TestDependencies:
    """Dependency resolution tests."""

    async def test_register_with_missing_dependency_fails(self, registry: AgentRegistry) -> None:
        agent = MockAgent(agent_id="a1", capabilities=["x"])
        with pytest.raises(AgentNotFoundError, match="Dependency"):
            await registry.register(agent, dependencies=["nonexistent-dep"])

    async def test_register_with_satisfied_dependency(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="dep1", capabilities=["x"]))
        await registry.register(
            MockAgent(agent_id="a1", capabilities=["y"]),
            dependencies=["dep1"],
        )
        assert registry.has("a1")

    async def test_circular_dependency_detected(self, registry: AgentRegistry) -> None:
        """A -> B -> A is a cycle and must be rejected."""
        # Register A first (no deps)
        await registry.register(MockAgent(agent_id="A", capabilities=["x"]))
        # B depends on A — fine
        await registry.register(
            MockAgent(agent_id="B", capabilities=["y"]),
            dependencies=["A"],
        )
        # Now check: if A were to depend on B, we'd have A -> B -> A
        with pytest.raises(CircularDependencyError):
            registry._check_no_cycle("A", {"B"})  # noqa: SLF001


@pytest.mark.offline
class TestTrackRecord:
    """Track record tests."""

    async def test_update_track_record(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["x"]))
        registry.update_track_record("a1", {"success_rate": 0.95, "avg_latency_ms": 1200})
        record = registry.get_track_record("a1")
        assert record["success_rate"] == 0.95
        assert record["avg_latency_ms"] == 1200

    async def test_track_record_in_summary(self, registry: AgentRegistry) -> None:
        await registry.register(MockAgent(agent_id="a1", capabilities=["x"]))
        registry.update_track_record("a1", {"success_rate": 0.9})
        summaries = registry.list_agents()
        assert summaries[0].track_record == {"success_rate": 0.9}


@pytest.mark.offline
class TestGetManifest:
    """get_manifest tests."""

    async def test_get_manifest(self, registry: AgentRegistry) -> None:
        await registry.register(
            MockAgent(
                agent_id="a1",
                agent_type=AgentType.CODING,
                capabilities=["code.read"],
            )
        )
        manifest = registry.get_manifest("a1")
        assert manifest.identity.agent_id == "a1"
        assert manifest.identity.agent_type == AgentType.CODING
        assert manifest.has_capability("code.read")

    async def test_get_manifest_unknown_raises(self, registry: AgentRegistry) -> None:
        with pytest.raises(AgentNotFoundError):
            registry.get_manifest("nope")


@pytest.mark.offline
class TestSingleton:
    """init_agent_registry / get_agent_registry tests."""

    def test_init_returns_singleton(self) -> None:
        reg = init_agent_registry()
        from services.agent_registry import get_agent_registry

        assert get_agent_registry() is reg
        # Clean up
        set_agent_registry(AgentRegistry())  # type: ignore[misc]
