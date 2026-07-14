"""SubprocessBridgeAgent — base class for agents that wrap external CLIs/daemons.

Used by CodingAgent (wraps the `claude` CLI) and DesktopAgent (wraps the
Hermes daemon). The agent spawns a subprocess and communicates via JSON-RPC
over stdin/stdout.

Phase 4: skeleton with the protocol stubbed. The full subprocess management
+ JSON-RPC implementation lands in Phase 9 (Claude Code) and Phase 10
(Hermes), where it's actually needed. The skeleton here gives the registry
a concrete base class to register and health-check.

Why stub? The architecture requires the GenericAgent interface to be
satisfied, but the actual subprocess invocation is the SOLE responsibility
of ``core/gateway/`` (INV-02). Subclasses use ``gateway.process.spawn()``
which itself wraps subprocess. Phase 9 will implement that gateway method.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from core.contracts.agent import (
    AgentContext,
    AgentIdentity,
    AgentState,
    MetricsReport,
)
from core.contracts.health import HealthReport
from core.contracts.permission import PermissionDecision, PermissionRequest
from core.contracts.task import TaskProgress, TaskRequest, TaskResult, TaskResultStatus
from core.logging import get_logger

_log = get_logger(__name__)


class SubprocessBridgeAgent:
    """Base class for subprocess-bridge agents.

    Subclasses MUST implement:
      - ``_spawn_command`` — returns the (executable, args) to launch the agent subprocess
      - ``_build_manifest`` — returns the capability manifest
      - ``_rpc_call`` — sends a JSON-RPC request to the subprocess and returns the response

    The base class handles:
      - Subprocess lifecycle (spawn, monitor, restart)
      - Health checks (is the subprocess alive?)
      - Metrics tracking (same as InProcessAgent)
      - Cancellation (sends a 'cancel' RPC)
    """

    def __init__(self, identity: AgentIdentity) -> None:
        self._identity = identity
        self._context: AgentContext | None = None
        self._initialized = False
        self._process: asyncio.subprocess.Process | None = None
        self._health: HealthReport = HealthReport.healthy()
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._tasks_cancelled = 0
        self._tokens_consumed = 0
        self._cost_usd = 0.0

    @property
    def identity(self) -> AgentIdentity:
        """Return this agent's identity."""
        return self._identity

    async def initialize(self, context: AgentContext) -> None:
        """Spawn the subprocess. Idempotent."""
        if self._initialized:
            return
        self._context = context
        # The actual spawn happens via gateway.process.spawn() in Phase 9/10.
        # Phase 4 stub: subclasses that need a real subprocess must implement
        # their own initialize() that calls gateway.process.spawn().
        await self._on_initialize()
        self._initialized = True
        _log.info("agent.subprocess_initialized", agent_id=self._identity.agent_id)

    async def _on_initialize(self) -> None:
        """Hook for subclasses. Default: no-op."""
        return

    async def shutdown(self, graceful: bool = True) -> None:
        """Terminate the subprocess. Idempotent. Never raises."""
        try:
            if not self._initialized:
                return
            if self._process is not None:
                if graceful:
                    try:
                        self._process.terminate()
                        await asyncio.wait_for(self._process.wait(), timeout=5.0)
                    except TimeoutError:
                        self._process.kill()
                else:
                    self._process.kill()
                self._process = None
            self._initialized = False
            _log.info(
                "agent.subprocess_shutdown", agent_id=self._identity.agent_id, graceful=graceful
            )
        except Exception:
            _log.exception("agent.subprocess_shutdown_failed", agent_id=self._identity.agent_id)

    async def discover_capabilities(self) -> Any:  # CapabilityManifest
        """Return the manifest. Subclasses implement _build_manifest."""
        if not self._initialized:
            raise RuntimeError(f"Agent {self._identity.agent_id} not initialized.")
        return await self._build_manifest()

    async def _build_manifest(self) -> Any:
        """Subclasses must implement."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _build_manifest()",
        )

    async def execute_task(self, request: TaskRequest) -> TaskResult:
        """Execute by sending an RPC to the subprocess."""
        if not self._initialized:
            raise RuntimeError(f"Agent {self._identity.agent_id} not initialized.")
        start = time.monotonic()
        try:
            result = await self._rpc_call("execute_task", {"request": request.model_dump()})
            task_result = TaskResult(**result) if isinstance(result, dict) else result
            if task_result.status == TaskResultStatus.SUCCESS:
                self._tasks_completed += 1
            elif task_result.status == TaskResultStatus.FAILURE:
                self._tasks_failed += 1
            return task_result
        except Exception as e:
            self._tasks_failed += 1
            _log.exception("agent.subprocess_task_failed", agent_id=self._identity.agent_id)
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.FAILURE,
                error=str(e),
                duration_s=time.monotonic() - start,
            )

    async def _rpc_call(self, method: str, params: dict[str, Any]) -> Any:
        """Send a JSON-RPC call to the subprocess. Subclasses implement."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _rpc_call()",
        )

    async def stream_progress(self, request: TaskRequest) -> AsyncIterator[TaskProgress]:
        """Default: emit RESULT with execute_task's output."""
        from core.contracts.task import TaskProgressKind

        result = await self.execute_task(request)
        yield TaskProgress(
            task_id=request.id,
            kind=TaskProgressKind.RESULT,
            message=f"{self._identity.agent_id} finished task",
            result=result,
        )

    async def cancel_task(self, task_id: str, reason: str) -> None:
        """Send a cancel RPC to the subprocess."""
        try:
            await self._rpc_call("cancel_task", {"task_id": task_id, "reason": reason})
            self._tasks_cancelled += 1
        except Exception:
            _log.exception("agent.subprocess_cancel_failed", agent_id=self._identity.agent_id)

    async def report_health(self) -> HealthReport:
        """Check if the subprocess is alive."""
        if not self._initialized:
            return HealthReport.unhealthy("not initialized")
        if self._process is None or self._process.returncode is not None:
            return HealthReport.unhealthy("subprocess not running")
        return self._health

    async def report_metrics(self) -> MetricsReport:
        """Return operational metrics."""
        return MetricsReport(
            agent_id=self._identity.agent_id,
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            tasks_cancelled=self._tasks_cancelled,
            tokens_consumed=self._tokens_consumed,
            cost_usd=self._cost_usd,
        )

    async def request_permission(self, request: PermissionRequest) -> PermissionDecision:
        """Forward to the permission manager (Phase 8). Default: ALLOW."""
        return PermissionDecision.ALLOW

    async def serialize_state(self) -> AgentState:
        """Default: empty state. Subprocess agents are usually stateless across crashes."""
        return AgentState(agent_id=self._identity.agent_id, format="1", data={})

    async def restore_state(self, state: AgentState) -> None:
        """Default: no-op. Subprocess agents restart fresh."""
        return
