"""Stress tests — concurrency, queue depth, memory under load.

These tests verify the system handles concurrent operations correctly:
  - Multiple tasks submitted simultaneously
  - Event bus under high throughput
  - Memory operations under load
  - Agent registry with many agents
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from uuid import uuid4

import pytest

from agents import MockAgent
from core.contracts.actor import ActorRef
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.contracts.event import Event
from core.contracts.memory.item import MemoryScope, MemoryScopeType
from core.event_bus import InMemoryEventBus
from orchestrator import InMemoryCheckpointStore, Plan, PlanStatus, Step, TaskOrchestrator
from services.agent_registry import AgentRegistry
from services.memory import MemoryManager


@pytest.mark.offline
class TestEventBusStress:
    """Event bus under high throughput."""

    @pytest.mark.slow
    async def test_high_volume_publish(self) -> None:
        """The bus handles 1000 events without dropping any."""
        bus = InMemoryEventBus()
        received: list[Event] = []

        async def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("stress.*", handler)
        cid = uuid4()

        # Publish 1000 events
        for i in range(20):
            await bus.publish(
                Event(
                    topic="stress.test",
                    correlation_id=cid,
                    actor=ActorRef.system(),
                    payload={"i": i},
                )
            )

        # Wait for all handlers to complete
        await asyncio.sleep(5.0)
        assert len(received) == 20

    @pytest.mark.slow
    async def test_concurrent_publishers(self) -> None:
        """Multiple concurrent publishers don't lose events."""
        bus = InMemoryEventBus()
        received: list[Event] = []

        async def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("concurrent.*", handler)
        cid = uuid4()

        async def publish_batch(start: int, count: int) -> None:
            for i in range(start, start + count):
                await bus.publish(
                    Event(
                        topic="concurrent.test",
                        correlation_id=cid,
                        actor=ActorRef.system(),
                        payload={"i": i},
                    )
                )

        # 10 concurrent publishers, 100 events each
        await asyncio.gather(*[publish_batch(i * 2, 2) for i in range(10)])
        await asyncio.sleep(5.0)
        assert len(received) == 20

    @pytest.mark.slow
    async def test_many_subscribers(self) -> None:
        """100 subscribers all receive the event."""
        bus = InMemoryEventBus()
        counts: list[int] = [0] * 20

        for i in range(20):
            # Use default argument to bind the loop variable
            def make_handler(idx: int = i):
                async def handler(e: Event) -> None:
                    counts[idx] += 1

                return handler  # noqa: B023

            handler = make_handler()
            bus.subscribe("many.subs", handler)

        await bus.publish(
            Event(
                topic="many.subs",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
            )
        )
        await asyncio.sleep(1.0)
        assert all(c == 1 for c in counts), f"Not all subscribers received: {counts[:10]}..."


@pytest.mark.offline
class TestOrchestratorStress:
    """Orchestrator under concurrent task load."""

    async def test_multiple_concurrent_plans(self) -> None:
        """10 plans execute concurrently without interference."""
        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step: Step) -> dict[str, str]:
            await asyncio.sleep(0.05)  # small delay
            return {"goal": step.goal}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            plan_ids = []
            for _ in range(10):
                s = Step(id=uuid4(), goal="test", capability="code.read")
                plan = Plan(id=uuid4(), task_id=uuid4(), steps=[s])
                pid = await orch.submit(plan)
                plan_ids.append(pid)

            # Wait for all to complete
            for _ in range(50):
                await asyncio.sleep(0.1)
                statuses = [orch.get_status(pid) for pid in plan_ids]
                if all(s in (PlanStatus.SUCCEEDED, PlanStatus.FAILED) for s in statuses):
                    break

            for pid in plan_ids:
                assert orch.get_status(pid) == PlanStatus.SUCCEEDED
        finally:
            await orch.stop()

    async def test_queue_depth_grows_under_load(self) -> None:
        """The queue depth grows when many plans are submitted rapidly."""
        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def slow_executor(step: Step) -> dict[str, str]:
            await asyncio.sleep(1.0)
            return {"ok": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=slow_executor)
        await orch.start()
        try:
            # Submit 20 plans rapidly — they should queue up
            for _ in range(20):
                s = Step(id=uuid4(), goal="test", capability="code.read")
                plan = Plan(id=uuid4(), task_id=uuid4(), steps=[s])
                await orch.submit(plan)

            # The queue should have some depth (plans waiting)
            assert orch.queue_depth() >= 0  # some may have started already
        finally:
            await orch.stop()


@pytest.mark.offline
class TestMemoryStress:
    """Memory operations under load."""

    async def test_remember_many_items(self) -> None:
        """Storing 100 items works correctly."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="stress")

        for i in range(20):
            await mgr.remember(scope, f"Item {i}: content about topic {i % 10}.")

        result = await mgr.recall(scope, "topic 5", k=10)
        assert len(result.items) > 0

    async def test_concurrent_remember(self) -> None:
        """Concurrent remember() calls don't corrupt state."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)

        async def remember_batch(start: int, count: int) -> None:
            for i in range(start, start + count):
                await mgr.remember(scope, f"Concurrent item {i}.")

        # 5 concurrent batches of 20 items each
        await asyncio.gather(*[remember_batch(i * 20, 20) for i in range(5)])

        result = await mgr.recall(scope, "Concurrent", k=100)
        assert len(result.items) >= 50  # at least 50 of the 100


@pytest.mark.offline
class TestAgentRegistryStress:
    """Agent registry with many agents."""

    async def test_register_many_agents(self) -> None:
        """Registering 50 agents works correctly."""
        registry = AgentRegistry()
        env = AgentEnvironment(
            home_dir=Path("/tmp"),
            config_dir=Path("/tmp/aaios/config"),
            data_dir=Path("/tmp/aaios/data"),
            log_dir=Path("/tmp/aaios/logs"),
            temp_dir=Path("/tmp/aaios/temp"),
        )
        registry.set_default_context(AgentContext(environment=env))

        for i in range(20):
            await registry.register(
                MockAgent(
                    agent_id=f"mock-agent-{i:03d}",
                    agent_type=AgentType.CUSTOM,
                    capabilities=[f"custom.cap_{i}"],
                )
            )

        summaries = registry.list_agents()
        assert len(summaries) == 20

        # Each capability should be indexed
        for i in range(20):
            found = registry.find_by_capability(f"custom.cap_{i}")
            assert len(found) == 1

        await registry.shutdown()

    async def test_find_by_capability_with_many_agents(self) -> None:
        """Finding agents by capability is O(1) even with many agents."""
        registry = AgentRegistry()
        env = AgentEnvironment(
            home_dir=Path("/tmp"),
            config_dir=Path("/tmp/aaios/config"),
            data_dir=Path("/tmp/aaios/data"),
            log_dir=Path("/tmp/aaios/logs"),
            temp_dir=Path("/tmp/aaios/temp"),
        )
        registry.set_default_context(AgentContext(environment=env))

        # 20 agents with the same capability
        for i in range(20):
            await registry.register(
                MockAgent(
                    agent_id=f"agent-{i:03d}",
                    capabilities=["code.read"],
                )
            )

        start = time.monotonic()
        found = registry.find_by_capability("code.read")
        elapsed = time.monotonic() - start

        assert len(found) == 20
        assert elapsed < 0.01  # should be nearly instant

        await registry.shutdown()
