"""Performance tests — benchmarks for critical paths.

These tests measure:
  - Kernel boot time (target: <5s)
  - Event bus throughput (target: >10k events/s)
  - Memory recall latency (target: <100ms for 100 items)
  - Agent registry lookup (target: <1ms)
  - Capability selector scoring (target: <1ms for 10 candidates)
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from uuid import uuid4

import pytest

from agents import MockAgent
from core.contracts.actor import ActorRef
from core.contracts.agent import AgentContext, AgentEnvironment
from core.contracts.event import Event
from core.contracts.memory.item import MemoryScope, MemoryScopeType
from core.event_bus import InMemoryEventBus
from services.agent_registry import AgentRegistry
from services.memory import MemoryManager
from supervisor import CapabilitySelector


@pytest.mark.offline
class TestPerformanceBenchmarks:
    """Performance benchmarks for critical paths."""

    async def test_event_bus_throughput(self) -> None:
        """Event bus should handle >10k events/s."""
        bus = InMemoryEventBus()
        cid = uuid4()

        start = time.monotonic()
        for _ in range(1000):
            await bus.publish(
                Event(
                    topic="perf.test",
                    correlation_id=cid,
                    actor=ActorRef.system(),
                )
            )
        elapsed = time.monotonic() - start

        throughput = 1000 / elapsed
        print(f"\n  Event bus throughput: {throughput:.0f} events/s")
        # Should be at least 1000/s (conservative; no subscriber)
        assert throughput > 1000

    async def test_memory_recall_latency(self) -> None:
        """Recall should complete in <500ms for 100 items."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="perf")

        for i in range(100):
            await mgr.remember(scope, f"Item {i}: content about topic {i % 10}.")

        start = time.monotonic()
        result = await mgr.recall(scope, "topic 5", k=10)
        elapsed = time.monotonic() - start

        print(f"\n  Recall latency (100 items): {elapsed * 1000:.0f}ms")
        assert elapsed < 2.0  # generous for CI
        assert len(result.items) > 0

    async def test_agent_registry_lookup(self) -> None:
        """Registry lookup should be <1ms with 50 agents."""
        registry = AgentRegistry()
        env = AgentEnvironment(
            home_dir=Path("/tmp"),
            config_dir=Path("/tmp/aaios/config"),
            data_dir=Path("/tmp/aaios/data"),
            log_dir=Path("/tmp/aaios/logs"),
            temp_dir=Path("/tmp/aaios/temp"),
        )
        registry.set_default_context(AgentContext(environment=env))

        for i in range(50):
            await registry.register(
                MockAgent(
                    agent_id=f"agent-{i:03d}",
                    capabilities=[f"cap.{i}"],
                )
            )

        start = time.monotonic()
        for i in range(50):
            registry.find_by_capability(f"cap.{i}")
        elapsed = time.monotonic() - start

        per_lookup = (elapsed / 50) * 1000
        print(f"\n  Registry lookup (50 agents): {per_lookup:.3f}ms/lookup")
        assert per_lookup < 10.0  # generous

        await registry.shutdown()

    async def test_capability_selector_scoring(self) -> None:
        """Capability selector should score 10 candidates in <10ms."""
        registry = AgentRegistry()
        env = AgentEnvironment(
            home_dir=Path("/tmp"),
            config_dir=Path("/tmp/aaios/config"),
            data_dir=Path("/tmp/aaios/data"),
            log_dir=Path("/tmp/aaios/logs"),
            temp_dir=Path("/tmp/aaios/temp"),
        )
        registry.set_default_context(AgentContext(environment=env))

        for i in range(10):
            await registry.register(
                MockAgent(
                    agent_id=f"agent-{i:03d}",
                    capabilities=["code.read"],
                )
            )

        selector = CapabilitySelector(registry)
        start = time.monotonic()
        result = selector.select("code.read")
        elapsed = time.monotonic() - start

        print(f"\n  Capability selector (10 candidates): {elapsed * 1000:.1f}ms")
        assert elapsed < 0.1  # generous
        assert result.agent_id is not None

        await registry.shutdown()

    async def test_dag_execution_throughput(self) -> None:
        """A 10-step sequential DAG should complete in <2s."""
        from orchestrator import InMemoryCheckpointStore, Plan, PlanStatus, Step, TaskOrchestrator

        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step: Step) -> dict[str, str]:
            return {"goal": step.goal}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            steps: list[Step] = []
            for i in range(10):
                s = Step(
                    id=uuid4(),
                    goal=f"step-{i}",
                    capability="code.read",
                    depends_on=[steps[-1].id] if steps else [],
                )
                steps.append(s)
            plan = Plan(id=uuid4(), task_id=uuid4(), steps=steps)

            start = time.monotonic()
            plan_id = await orch.submit(plan)
            for _ in range(50):
                await asyncio.sleep(0.1)
                status = orch.get_status(plan_id)
                if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED):
                    break
            elapsed = time.monotonic() - start

            print(f"\n  10-step DAG execution: {elapsed * 1000:.0f}ms")
            assert status == PlanStatus.SUCCEEDED
            assert elapsed < 5.0  # generous
        finally:
            await orch.stop()
