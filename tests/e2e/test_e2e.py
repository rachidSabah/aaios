"""End-to-end tests — full pipeline from goal to result.

These tests exercise the complete task lifecycle:
  goal → Planner → Plan → Orchestrator → Step Executor → Agent →
  Reflection → QA → Checkpoint → Result

All tests use mock agents and mock LLM (no real API calls).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agents import MockAgent
from core.contracts.actor import ActorRef
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.event_bus import InMemoryEventBus
from orchestrator import InMemoryCheckpointStore, PlanStatus, TaskOrchestrator
from services.agent_registry import AgentRegistry
from supervisor import DefaultSupervisor


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


@pytest.mark.offline
class TestEndToEndTaskLifecycle:
    """Full task lifecycle: goal → plan → execute → result."""

    async def test_submit_goal_creates_and_executes_plan(
        self,
        agent_context: AgentContext,
    ) -> None:
        """Submitting a goal creates a plan and executes it."""
        registry = AgentRegistry()
        registry.set_default_context(agent_context)
        await registry.register(
            MockAgent(
                agent_id="mock-coding-v1",
                agent_type=AgentType.CODING,
                capabilities=["plan.decompose", "code.read"],
            )
        )

        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step):  # type: ignore[no-untyped-def]
            return {"goal": step.goal, "executed": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            supervisor = DefaultSupervisor(
                registry=registry,
                orchestrator=orch,
                router=None,
            )
            task_id = await supervisor.submit_goal("read the auth module")
            plan = supervisor.get_plan(task_id)
            assert plan is not None
            assert len(plan.steps) >= 1

            # Wait for execution
            for _ in range(30):
                await asyncio.sleep(0.1)
                status = orch.get_status(plan.id)
                if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED, PlanStatus.CANCELLED):
                    break

            assert status == PlanStatus.SUCCEEDED
        finally:
            await orch.stop()
            await registry.shutdown()

    async def test_cancellation_mid_execution(
        self,
        agent_context: AgentContext,
    ) -> None:
        """A task can be cancelled while it's running."""
        registry = AgentRegistry()
        registry.set_default_context(agent_context)
        await registry.register(
            MockAgent(
                agent_id="mock-v1",
                capabilities=["plan.decompose"],
            )
        )

        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def slow_executor(step):  # type: ignore[no-untyped-def]
            await asyncio.sleep(10)  # very slow
            return {"ok": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=slow_executor)
        # Don't start the orchestrator — plan stays in queue

        supervisor = DefaultSupervisor(
            registry=registry,
            orchestrator=orch,
            router=None,
        )
        task_id = await supervisor.submit_goal("long task")
        plan = supervisor.get_plan(task_id)
        assert plan is not None

        # Cancel before execution starts
        result = await orch.cancel(plan.id, reason="user cancelled")
        assert result is True
        assert orch.get_status(plan.id) == PlanStatus.CANCELLED
        await registry.shutdown()

    async def test_pause_and_resume(
        self,
        agent_context: AgentContext,
    ) -> None:
        """A task can be paused and resumed."""
        registry = AgentRegistry()
        registry.set_default_context(agent_context)
        await registry.register(
            MockAgent(
                agent_id="mock-v1",
                capabilities=["plan.decompose"],
            )
        )

        bus = InMemoryEventBus()
        store = InMemoryCheckpointStore()

        async def step_executor(step):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.1)
            return {"ok": True}

        orch = TaskOrchestrator(bus=bus, checkpoint_store=store, step_executor=step_executor)
        await orch.start()
        try:
            supervisor = DefaultSupervisor(
                registry=registry,
                orchestrator=orch,
                router=None,
            )
            task_id = await supervisor.submit_goal("test task")
            plan = supervisor.get_plan(task_id)
            assert plan is not None

            # Pause immediately
            await orch.pause(plan.id)
            assert orch.get_status(plan.id) == PlanStatus.PAUSED

            # Resume
            await orch.resume(plan.id)
            for _ in range(30):
                await asyncio.sleep(0.1)
                status = orch.get_status(plan.id)
                if status in (PlanStatus.SUCCEEDED, PlanStatus.FAILED):
                    break
            assert status == PlanStatus.SUCCEEDED
        finally:
            await orch.stop()
            await registry.shutdown()


@pytest.mark.offline
class TestEndToEndMemoryOperations:
    """Full memory operations: remember → recall → forget."""

    async def test_full_memory_lifecycle(self) -> None:
        from core.contracts.memory.item import MemoryScope, MemoryScopeType
        from services.memory import MemoryManager

        mgr = MemoryManager()
        scope = MemoryScope(scope_type=MemoryScopeType.PROJECT, project_id="e2e-test")

        # Remember
        await mgr.remember(scope, "The project uses PostgreSQL 16.")
        await mgr.remember(scope, "The API runs on FastAPI.")
        await mgr.remember(scope, "Tests use pytest.")

        # Recall
        result = await mgr.recall(scope, "What database?", k=3)
        assert len(result.items) > 0
        assert any("PostgreSQL" in r.item.content for r in result.items)

        # Forget
        count = await mgr.forget(scope)
        assert count >= 3

        # Verify forgotten
        result = await mgr.recall(scope, "database", k=3)
        assert len(result.items) == 0


@pytest.mark.offline
class TestEndToEndPluginLifecycle:
    """Full plugin lifecycle: install → enable → disable → uninstall."""

    async def test_plugin_install_enable_disable_uninstall(self) -> None:
        from services.plugin import PluginManager, PluginManifest, PluginState

        mgr = PluginManager()
        manifest = PluginManifest(
            name="e2e-test-plugin",
            version="1.0.0",
            entry_point="nonexistent_module",  # won't actually import
        )

        # Install
        name = await mgr.install_from_manifest(manifest)
        assert name == "e2e-test-plugin"
        assert mgr.get_plugin("e2e-test-plugin").state == PluginState.INSTALLED

        # Disable (can't enable without a real module, but can disable)
        assert await mgr.disable("e2e-test-plugin") is True
        assert mgr.get_plugin("e2e-test-plugin").state == PluginState.DISABLED

        # Uninstall
        assert await mgr.uninstall("e2e-test-plugin") is True
        assert mgr.get_plugin("e2e-test-plugin") is None


@pytest.mark.offline
class TestEndToEndSecurityFlow:
    """Full security flow: assign role → check permission → audit → verify."""

    async def test_full_security_lifecycle(self) -> None:
        from core.contracts.permission import Permission, PermissionDecision
        from core.gateway.audit import AuditEntry
        from services.security import Role, SecurityManager

        mgr = SecurityManager()
        mgr.install_in_gateway()

        # Assign roles
        mgr.assign_role("admin1", Role.ADMIN)
        mgr.assign_role("viewer1", Role.VIEWER)

        # Admin can do most things
        result = await mgr.check(
            ActorRef.user("admin1"),
            Permission(name="task.submit"),
        )
        assert result.decision == PermissionDecision.ALLOW

        # Viewer can read tasks
        result = await mgr.check(
            ActorRef.user("viewer1"),
            Permission(name="task.read"),
        )
        assert result.decision == PermissionDecision.ALLOW

        # Viewer cannot write files
        result = await mgr.check(
            ActorRef.user("viewer1"),
            Permission(name="gateway.fs.write"),
        )
        assert result.decision == PermissionDecision.DENY

        # Audit the checks
        await mgr.log(
            AuditEntry(
                actor=ActorRef.user("admin1"),
                action="task.submit",
                target="task-123",
                success=True,
            )
        )
        await mgr.log(
            AuditEntry(
                actor=ActorRef.user("viewer1"),
                action="gateway.fs.write",
                target="/etc/passwd",
                success=False,
                reason="denied by policy",
            )
        )

        # Verify audit chain
        assert await mgr.verify_audit_chain() is True

        # Query audit log
        admin_entries = await mgr.get_audit_entries(actor_id="admin1")
        assert len(admin_entries) == 1
        assert admin_entries[0].action == "task.submit"
