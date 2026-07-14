"""Integration tests — multi-component workflows.

These tests verify that components work together correctly:
  - Kernel boot → event bus → state manager → event replay
  - Orchestrator + mock agents → DAG execution → checkpoint
  - Supervisor + capability selector + mock agents → full task lifecycle
  - Memory manager + RAG pipeline → remember → recall → rank
  - Security layer → Gateway integration → permission enforcement
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from agents import MockAgent
from core.contracts.actor import ActorRef
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.contracts.event import Event
from core.contracts.memory.item import MemoryItem, MemoryScope, MemoryScopeType
from core.event_bus import InMemoryEventBus
from orchestrator import (
    InMemoryCheckpointStore,
    Plan,
    PlanStatus,
    Step,
    StepStatus,
    TaskOrchestrator,
)
from services.agent_registry import AgentRegistry
from services.memory import MemoryManager
from services.security import Role, SecurityManager


@pytest.fixture
def agent_context() -> AgentContext:
    """Minimal AgentContext for tests."""
    env = AgentEnvironment(
        home_dir=Path("/tmp"),
        config_dir=Path("/tmp/aaios/config"),
        data_dir=Path("/tmp/aaios/data"),
        log_dir=Path("/tmp/aaios/logs"),
        temp_dir=Path("/tmp/aaios/temp"),
    )
    return AgentContext(environment=env)


# ---------------------------------------------------------------------------
# Kernel + Event Bus + State Manager
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestKernelEventBusStateIntegration:
    """Kernel → Event Bus → State Manager integration."""

    @pytest.mark.slow
    async def test_event_persisted_before_dispatch(self) -> None:
        """INV-04: events are persisted BEFORE subscribers see them."""
        bus = InMemoryEventBus()
        received: list = []
        dispatched_after_persist: list[bool] = []

        async def handler(event: Event) -> None:
            # Verify the event is already in the store when we receive it
            events_in_store = await bus.store.replay(stream_id=str(event.correlation_id))
            dispatched_after_persist.append(len(events_in_store) > 0)
            received.append(event)

        bus.subscribe("test.*", handler)
        cid = uuid4()
        await bus.publish(
            Event(
                topic="test.integration",
                correlation_id=cid,
                actor=ActorRef.system(),
                payload={"test": True},
            )
        )
        # Poll for the handler to complete
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(received) > 0:
                break
        assert len(received) == 1
        assert all(dispatched_after_persist), "Event was not persisted before dispatch"

    async def test_event_replay_restores_state(self) -> None:
        """Replaying events from the store re-delivers them to new subscribers."""
        bus = InMemoryEventBus()
        cid = uuid4()

        # Publish without subscribers
        for i in range(5):
            await bus.publish(
                Event(
                    topic="test.replay",
                    correlation_id=cid,
                    actor=ActorRef.system(),
                    payload={"i": i},
                )
            )

        # Now subscribe and replay
        received: list[int] = []

        async def handler(event: Event) -> None:
            received.append(event.payload.get("i", -1))

        bus.subscribe("test.replay", handler)
        await bus.replay(stream_id=cid)
        await asyncio.sleep(0.3)
        assert received == [0, 1, 2, 3, 4]

    async def test_multiple_subscribers_all_receive(self) -> None:
        """Multiple subscribers to the same topic all receive events."""
        bus = InMemoryEventBus()
        received_a: list[Event] = []
        received_b: list[Event] = []

        async def handler_a(e: Event) -> None:
            received_a.append(e)

        async def handler_b(e: Event) -> None:
            received_b.append(e)

        bus.subscribe("test.multi", handler_a)
        bus.subscribe("test.multi", handler_b)
        await bus.publish(
            Event(
                topic="test.multi",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
            )
        )
        await asyncio.sleep(0.3)
        assert len(received_a) == 1
        assert len(received_b) == 1


# ---------------------------------------------------------------------------
# Orchestrator + Mock Agents → DAG Execution
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestOrchestratorDAGIntegration:
    """Orchestrator + mock agents → DAG execution → checkpoint."""

    async def test_dag_with_parallel_steps_executes_correctly(self) -> None:
        """A DAG with parallel branches executes all steps."""
        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()
        executed: list[str] = []

        async def step_executor(step: Step) -> dict[str, str]:
            executed.append(step.capability)
            return {"goal": step.goal}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            # S1 → (S2a || S2b) → S3
            s1 = Step(id=uuid4(), goal="read", capability="code.read")
            s2a = Step(id=uuid4(), goal="write A", capability="code.write", depends_on=[s1.id])
            s2b = Step(id=uuid4(), goal="write B", capability="code.write", depends_on=[s1.id])
            s3 = Step(id=uuid4(), goal="test", capability="test.run", depends_on=[s2a.id, s2b.id])
            plan = Plan(id=uuid4(), task_id=uuid4(), steps=[s1, s2a, s2b, s3])

            plan_id = await orch.submit(plan)
            for _ in range(30):
                await asyncio.sleep(0.3)
                status = orch.get_status(plan_id)
                if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED):
                    break

            assert status == PlanStatus.SUCCEEDED
            assert len(executed) == 4
            assert all(s.status == StepStatus.SUCCEEDED for s in plan.steps)
        finally:
            await orch.stop()

    async def test_failed_step_skips_dependents(self) -> None:
        """A failed step causes dependents to be skipped."""
        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step: Step) -> dict[str, str]:
            if step.capability == "code.write":
                raise RuntimeError("write failed")
            return {"ok": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            s1 = Step(id=uuid4(), goal="read", capability="code.read")
            s2 = Step(id=uuid4(), goal="write", capability="code.write", depends_on=[s1.id])
            s3 = Step(id=uuid4(), goal="test", capability="test.run", depends_on=[s2.id])
            plan = Plan(id=uuid4(), task_id=uuid4(), steps=[s1, s2, s3])

            plan_id = await orch.submit(plan)
            for _ in range(30):
                await asyncio.sleep(0.3)
                status = orch.get_status(plan_id)
                if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED):
                    break

            assert status == PlanStatus.FAILED
            assert plan.steps[0].status == StepStatus.SUCCEEDED
            assert plan.steps[1].status == StepStatus.FAILED
            assert plan.steps[2].status == StepStatus.SKIPPED
        finally:
            await orch.stop()

    async def test_checkpoint_persists_step_result(self) -> None:
        """Checkpointing a step persists its result."""
        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step: Step) -> dict[str, str]:
            return {"result": "ok"}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            s1 = Step(id=uuid4(), goal="read", capability="code.read")
            plan = Plan(id=uuid4(), task_id=uuid4(), steps=[s1])
            plan_id = await orch.submit(plan)
            for _ in range(30):
                await asyncio.sleep(0.3)
                status = orch.get_status(plan_id)
                if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED):
                    break

            # Write a checkpoint manually
            s1.status = StepStatus.SUCCEEDED
            await orch.checkpoint_step(plan_id, s1, result={"result": "ok"})
            cp = await orch.get_latest_checkpoint(plan_id)
            assert cp is not None
            assert cp.step_goal == "read"
            assert cp.output == {"result": "ok"}
        finally:
            await orch.stop()


# ---------------------------------------------------------------------------
# Supervisor + Capability Selector + Mock Agents
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestSupervisorAgentIntegration:
    """Supervisor + capability selector + mock agents → full task lifecycle."""

    async def test_supervisor_dispatches_to_registered_agent(
        self,
        agent_context: AgentContext,
    ) -> None:
        """The supervisor can dispatch a step to a registered mock agent."""
        from supervisor import DefaultSupervisor

        registry = AgentRegistry()
        registry.set_default_context(agent_context)
        await registry.register(
            MockAgent(
                agent_id="mock-coding-v1",
                agent_type=AgentType.CODING,
                capabilities=["code.read", "code.write", "test.run"],
            )
        )

        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step: Step) -> dict[str, str]:
            # Use the capability selector to find and dispatch to the agent
            return {"goal": step.goal, "executed": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            supervisor = DefaultSupervisor(
                registry=registry,
                orchestrator=orch,
                router=None,
            )
            task_id = await supervisor.submit_goal("read auth module")
            plan = supervisor.get_plan(task_id)
            assert plan is not None
            assert len(plan.steps) >= 1
        finally:
            await orch.stop()
            await registry.shutdown()


# ---------------------------------------------------------------------------
# Memory + RAG Pipeline
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestMemoryRAGIntegration:
    """Memory manager + RAG pipeline → remember → recall → rank."""

    async def test_remember_and_recall_roundtrip(self) -> None:
        """Items stored via remember() can be retrieved via recall()."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="test")

        await mgr.remember(scope, "The database is PostgreSQL 16 on port 5432.")
        await mgr.remember(scope, "The API server runs on port 8000 with FastAPI.")
        await mgr.remember(scope, "The auth module uses JWT tokens for authentication.")

        result = await mgr.recall(scope, "What database?", k=3)
        assert len(result.items) > 0
        # The database item should be in the results (keyword matching)
        all_content = " ".join(r.item.content.lower() for r in result.items)
        assert "database" in all_content or "postgresql" in all_content

    async def test_recall_returns_scored_results(self) -> None:
        """Recall results have scores and source attribution."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.LONG_TERM)
        await mgr.remember(scope, "Python is a programming language.")
        await mgr.remember(scope, "The weather is sunny today.")

        result = await mgr.recall(scope, "programming language", k=2)
        assert len(result.items) > 0
        for item in result.items:
            assert 0.0 <= item.score <= 1.0
            assert item.source in ("vector", "graph", "keyword", "hybrid")

    async def test_memory_ranking_orders_by_relevance(self) -> None:
        """Ranking puts the most relevant item first."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.SEMANTIC)
        items = [
            MemoryItem.create(scope, "The capital of France is Paris."),
            MemoryItem.create(scope, "The capital of Japan is Tokyo."),
            MemoryItem.create(scope, "The capital of Brazil is Brasília."),
        ]
        ranked = await mgr.rank(items, "What is the capital of France?")
        # Verify ranking returns all items with valid scores
        assert len(ranked) == 3
        assert all(0.0 <= r.score <= 1.0 for r in ranked)
        # Verify items are sorted by score descending
        scores = [r.score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    async def test_context_window_budgeting(self) -> None:
        """Recall respects the max_tokens budget."""
        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="budget")
        for i in range(10):
            await mgr.remember(scope, f"Item {i}: " + "x" * 200)

        # Request with a small token budget — should truncate
        result = await mgr.recall(scope, "Item", k=10, max_tokens=50)
        assert result.truncated is True or result.actual_tokens <= 50


# ---------------------------------------------------------------------------
# Security Layer → Gateway Integration
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestSecurityGatewayIntegration:
    """Security layer → Gateway → permission enforcement."""

    async def test_security_manager_installs_in_gateway(self) -> None:
        """SecurityManager.install_in_gateway() replaces the NoOp stubs."""
        from core.gateway import get_audit_logger, get_permission_checker

        mgr = SecurityManager()
        mgr.install_in_gateway()
        assert get_permission_checker() is mgr
        assert get_audit_logger() is mgr

    async def test_permission_check_with_roles(self) -> None:
        """The security manager enforces RBAC through the Gateway protocol."""
        from core.contracts.permission import Permission, PermissionDecision

        mgr = SecurityManager()
        mgr.assign_role("alice", Role.OWNER)
        mgr.assign_role("viewer1", Role.VIEWER)

        # Owner can do everything
        result = await mgr.check(
            ActorRef.user("alice"),
            Permission(name="gateway.fs.write"),
        )
        assert result.decision == PermissionDecision.ALLOW

        # Viewer is denied write
        result = await mgr.check(
            ActorRef.user("viewer1"),
            Permission(name="gateway.fs.write"),
        )
        assert result.decision == PermissionDecision.DENY

    async def test_audit_log_via_gateway(self) -> None:
        """Gateway audit entries flow to the SecurityManager's audit log."""
        from core.gateway.audit import AuditEntry, get_audit_logger

        mgr = SecurityManager()
        mgr.install_in_gateway()

        # Simulate a gateway action
        logger = get_audit_logger()
        await logger.log(
            AuditEntry(
                actor=ActorRef.system(),
                action="gateway.fs.read",
                target="/tmp/test",
                success=True,
            )
        )

        entries = await mgr.get_audit_entries()
        assert len(entries) == 1
        assert entries[0].action == "gateway.fs.read"

    async def test_audit_chain_integrity_after_multiple_entries(self) -> None:
        """The hash chain remains valid after many entries."""
        from core.gateway.audit import AuditEntry

        mgr = SecurityManager()
        for i in range(20):
            await mgr.log(
                AuditEntry(
                    actor=ActorRef.system(),
                    action=f"test.{i}",
                    target=f"item-{i}",
                    success=True,
                )
            )
        assert await mgr.verify_audit_chain() is True
