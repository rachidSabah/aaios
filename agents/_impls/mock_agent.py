"""Mock agent implementation — for testing the registry end-to-end.

This agent satisfies the ``GenericAgent`` interface (via ``InProcessAgent``)
without needing any real LLM calls. It's used by:
  - Unit tests for the Agent Registry
  - Phase 5 (Task Orchestrator) tests
  - Phase 8 (Supervisor) tests, until real agents are available
  - The CLI's ``aaios dev`` smoke test

The mock agent advertises configurable capabilities and returns a
configurable result for ``execute_task``.
"""

from __future__ import annotations

from agents._base.in_process import InProcessAgent
from core.contracts.agent import (
    AgentIdentity,
    AgentState,
    AgentType,
    Capability,
    CapabilityManifest,
)
from core.contracts.health import HealthState
from core.contracts.task import TaskRequest, TaskResult, TaskResultStatus
from core.logging import get_logger

_log = get_logger(__name__)


class MockAgent(InProcessAgent):
    """A configurable mock agent for testing.

    Example:
        agent = MockAgent(
            agent_id='mock-coding-v1',
            agent_type=AgentType.CODING,
            capabilities=['code.read', 'code.write', 'test.run'],
            result_status=TaskResultStatus.SUCCESS,
            result_output={'files': ['auth.py']},
        )
        await registry.register(agent)

        # When the supervisor dispatches a task:
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.SUCCESS
        assert result.output == {'files': ['auth.py']}
    """

    def __init__(
        self,
        *,
        agent_id: str,
        agent_type: AgentType = AgentType.CUSTOM,
        implementation_name: str | None = None,
        version: str = "1.0.0",
        vendor: str = "AAiOS (mock)",
        capabilities: list[str] | None = None,
        result_status: TaskResultStatus = TaskResultStatus.SUCCESS,
        result_output: object = None,
        result_error: str | None = None,
        initial_health: HealthState = HealthState.HEALTHY,
        fail_initialize: bool = False,
        latency_s: float = 0.0,
    ) -> None:
        identity = AgentIdentity(
            agent_id=agent_id,
            agent_type=agent_type,
            implementation_name=implementation_name or f"Mock {agent_type.value.title()} Agent",
            version=version,
            vendor=vendor,
            signature=None,
        )
        super().__init__(identity)
        self._capabilities: list[str] = capabilities or []
        self._result_status: TaskResultStatus = result_status
        self._result_output: object = result_output
        self._result_error: str | None = result_error
        self._fail_initialize: bool = fail_initialize
        self._latency_s: float = latency_s
        self._set_health(initial_health)
        # Track execute_task calls for test assertions
        self.execute_calls: list[TaskRequest] = []

    async def _on_initialize(self) -> None:
        """Hook: optionally fail to test error handling."""
        if self._fail_initialize:
            raise RuntimeError("Mock agent configured to fail initialization.")

    async def _build_manifest(self) -> CapabilityManifest:
        """Build a manifest from the configured capabilities."""
        return CapabilityManifest(
            identity=self._identity,
            capabilities=[
                Capability(
                    namespace=cap,
                    description=f"Mock capability {cap}",
                    input_schema={},
                    output_schema={},
                )
                for cap in self._capabilities
            ],
        )

    async def _execute(self, request: TaskRequest) -> TaskResult:
        """Return the configured result, optionally after a delay."""
        self.execute_calls.append(request)
        if self._latency_s > 0:
            import asyncio

            await asyncio.sleep(self._latency_s)
        return TaskResult(
            task_id=request.id,
            status=self._result_status,
            output=self._result_output,
            error=self._result_error,
            duration_s=self._latency_s,
        )

    # Expose state for test assertions
    async def serialize_state(self) -> AgentState:
        """Include execute_calls count in state (for testing)."""
        return AgentState(
            agent_id=self._identity.agent_id,
            format="mock-1",
            data={
                "execute_calls_count": len(self.execute_calls),
                "tasks_completed": self._tasks_completed,
                "tasks_failed": self._tasks_failed,
            },
        )

    async def restore_state(self, state: AgentState) -> None:
        """Restore state (for testing)."""
        if state.format != "mock-1":
            from core.contracts.agent import StateIncompatibleError

            raise StateIncompatibleError(self._identity.agent_id, "mock-1", state.format)
        # Don't restore execute_calls (we're a fresh instance)


__all__ = ["MockAgent"]
