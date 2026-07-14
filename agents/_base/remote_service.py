"""RemoteServiceAgent — base class for agents that talk to a remote service.

Used for heavy agents deployed separately (e.g. a GPU-bound VisionAgent on
a dedicated box). Communication is via HTTP/gRPC through the Gateway.

Phase 4: skeleton. The full implementation lands in a later phase when
remote agents are actually needed.
"""

from __future__ import annotations

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
from core.contracts.task import (
    TaskProgress,
    TaskProgressKind,
    TaskRequest,
    TaskResult,
    TaskResultStatus,
)
from core.logging import get_logger

_log = get_logger(__name__)


class RemoteServiceAgent:
    """Base class for remote-service agents.

    Subclasses MUST implement:
      - ``_endpoint`` — the base URL of the remote agent service
      - ``_build_manifest`` — returns the capability manifest
      - ``_call_remote`` — sends a request to the remote service

    The base class handles health checks (HTTP probe), metrics, cancellation.
    """

    def __init__(self, identity: AgentIdentity, endpoint: str) -> None:
        self._identity = identity
        self._endpoint = endpoint.rstrip("/")
        self._context: AgentContext | None = None
        self._initialized = False
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
        """Verify the remote endpoint is reachable. Idempotent."""
        if self._initialized:
            return
        self._context = context
        # Phase 4 stub: real implementation will do a GET /healthz on the endpoint
        self._initialized = True
        _log.info(
            "agent.remote_initialized", agent_id=self._identity.agent_id, endpoint=self._endpoint
        )

    async def shutdown(self, graceful: bool = True) -> None:
        """No-op for remote agents (the service keeps running)."""
        self._initialized = False
        _log.info("agent.remote_shutdown", agent_id=self._identity.agent_id)

    async def discover_capabilities(self) -> Any:
        """Fetch the manifest from the remote service."""
        if not self._initialized:
            raise RuntimeError(f"Agent {self._identity.agent_id} not initialized.")
        return await self._build_manifest()

    async def _build_manifest(self) -> Any:
        """Subclasses must implement (or fetch from the remote service)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _build_manifest()",
        )

    async def execute_task(self, request: TaskRequest) -> TaskResult:
        """Forward the task to the remote service."""
        if not self._initialized:
            raise RuntimeError(f"Agent {self._identity.agent_id} not initialized.")
        start = time.monotonic()
        try:
            result = await self._call_remote("execute_task", request.model_dump())
            task_result = TaskResult(**result) if isinstance(result, dict) else result
            if task_result.status == TaskResultStatus.SUCCESS:
                self._tasks_completed += 1
            elif task_result.status == TaskResultStatus.FAILURE:
                self._tasks_failed += 1
            return task_result
        except Exception as e:
            self._tasks_failed += 1
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.FAILURE,
                error=str(e),
                duration_s=time.monotonic() - start,
            )

    async def _call_remote(self, method: str, payload: dict[str, Any]) -> Any:
        """Send a request to the remote service. Subclasses implement."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _call_remote()",
        )

    async def stream_progress(self, request: TaskRequest) -> AsyncIterator[TaskProgress]:
        """Default: emit RESULT with execute_task's output."""
        result = await self.execute_task(request)
        yield TaskProgress(
            task_id=request.id,
            kind=TaskProgressKind.RESULT,
            message=f"{self._identity.agent_id} finished task",
            result=result,
        )

    async def cancel_task(self, task_id: str, reason: str) -> None:
        """Send a cancel request to the remote service."""
        try:
            await self._call_remote("cancel_task", {"task_id": task_id, "reason": reason})
            self._tasks_cancelled += 1
        except Exception:
            _log.exception("agent.remote_cancel_failed", agent_id=self._identity.agent_id)

    async def report_health(self) -> HealthReport:
        """Probe the remote service's /healthz."""
        if not self._initialized:
            return HealthReport.unhealthy("not initialized")
        # Phase 4 stub: real implementation will HTTP-probe the endpoint
        return HealthReport.healthy()

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
        """Remote agents are stateless from the local POV."""
        return AgentState(agent_id=self._identity.agent_id, format="1", data={})

    async def restore_state(self, state: AgentState) -> None:
        """No-op for remote agents."""
        return
