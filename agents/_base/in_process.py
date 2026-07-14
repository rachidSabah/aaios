"""InProcessAgent — base class for in-process Python agents.

Computationally cheap, pure-Python, no isolation needed. Examples:
ReflectionAgent, QAAgent (deterministic parts), MemoryAgent, WorkflowAgent.

This base class provides:
  - Identity storage
  - Health tracking (defaults to healthy)
  - Metrics tracking (tasks_completed, tasks_failed, latency)
  - State serialization (defaults to empty state)
  - The ``_emit_lifecycle_events`` helper for the ``agent.task.started``
    / ``agent.task.finished`` events that every execute_task call must emit.

Subclasses must implement:
  - ``initialize`` (acquire resources)
  - ``discover_capabilities`` (return CapabilityManifest)
  - ``execute_task`` (the actual work)
  - ``stream_progress`` (or inherit the default which just yields execute_task's result)
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from core.contracts.agent import (
    AgentContext,
    AgentIdentity,
    AgentState,
    MetricsReport,
)
from core.contracts.event import Event, EventTopic
from core.contracts.health import HealthReport, HealthState
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


class InProcessAgent:
    """Base class for in-process agents.

    Subclasses MUST set ``self._identity`` in ``__init__`` (or override the
    ``identity`` property) and implement ``_build_manifest``.
    """

    def __init__(self, identity: AgentIdentity) -> None:
        self._identity: AgentIdentity = identity
        self._context: AgentContext | None = None
        self._initialized: bool = False
        self._health: HealthReport = HealthReport.healthy()
        self._tasks_completed: int = 0
        self._tasks_failed: int = 0
        self._tasks_cancelled: int = 0
        self._latencies: deque[float] = deque(maxlen=1000)  # ms, last 1000 tasks
        self._tokens_consumed: int = 0
        self._cost_usd: float = 0.0
        self._cancellation_requested: set[str] = set()  # task_ids

    # ------------------------------------------------------------------
    # Identity & lifecycle
    # ------------------------------------------------------------------

    @property
    def identity(self) -> AgentIdentity:
        """Return this agent's identity."""
        return self._identity

    async def initialize(self, context: AgentContext) -> None:
        """Initialize the agent. Idempotent."""
        if self._initialized:
            return
        self._context = context
        await self._on_initialize()
        self._initialized = True
        _log.info("agent.initialized", agent_id=self._identity.agent_id)

    async def _on_initialize(self) -> None:
        """Hook for subclasses to acquire resources. Default: no-op."""
        return

    async def shutdown(self, graceful: bool = True) -> None:
        """Release resources. Idempotent. Never raises."""
        try:
            if not self._initialized:
                return
            await self._on_shutdown(graceful=graceful)
            self._initialized = False
            _log.info("agent.shutdown", agent_id=self._identity.agent_id, graceful=graceful)
        except Exception:
            _log.exception("agent.shutdown_failed", agent_id=self._identity.agent_id)

    async def _on_shutdown(self, *, graceful: bool = True) -> None:
        """Hook for subclasses to release resources. Default: no-op."""
        return

    # ------------------------------------------------------------------
    # Capability discovery
    # ------------------------------------------------------------------

    async def discover_capabilities(self) -> Any:  # CapabilityManifest
        """Return the capability manifest. Subclasses must implement _build_manifest."""
        if not self._initialized:
            raise RuntimeError(f"Agent {self._identity.agent_id} not initialized.")
        return await self._build_manifest()

    async def _build_manifest(self) -> Any:  # CapabilityManifest
        """Build the capability manifest. Subclasses must implement."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _build_manifest()",
        )

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def execute_task(self, request: TaskRequest) -> TaskResult:
        """Execute a task. Emits lifecycle events. Tracks metrics."""
        if not self._initialized:
            raise RuntimeError(f"Agent {self._identity.agent_id} not initialized.")
        await self._emit_event(EventTopic.AGENT_DISPATCHED, request)
        await self._emit_event(EventTopic.STEP_STARTED, request)
        start = time.monotonic()
        try:
            if request.id.hex in self._cancellation_requested:
                self._cancellation_requested.discard(request.id.hex)
                return TaskResult(
                    task_id=request.id,
                    status=TaskResultStatus.CANCELLED,
                    error="cancelled before start",
                    duration_s=0.0,
                )
            result = await self._execute(request)
            duration_ms = (time.monotonic() - start) * 1000
            self._latencies.append(duration_ms)
            if result.status == TaskResultStatus.SUCCESS:
                self._tasks_completed += 1
            elif result.status == TaskResultStatus.FAILURE:
                self._tasks_failed += 1
            elif result.status == TaskResultStatus.CANCELLED:
                self._tasks_cancelled += 1
            await self._emit_event(EventTopic.STEP_COMPLETED, request, result.status.value)
            return result
        except Exception as e:
            self._tasks_failed += 1
            _log.exception(
                "agent.task_failed", agent_id=self._identity.agent_id, task_id=str(request.id)
            )
            await self._emit_event(EventTopic.STEP_FAILED, request, str(e))
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.FAILURE,
                error=str(e),
                duration_s=time.monotonic() - start,
            )

    async def _execute(self, request: TaskRequest) -> TaskResult:
        """Subclasses must implement the actual task logic."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _execute()",
        )

    async def stream_progress(self, request: TaskRequest) -> AsyncIterator[TaskProgress]:
        """Default: emit a STARTED event, then a RESULT event with the final result."""
        yield TaskProgress(
            task_id=request.id,
            kind=TaskProgressKind.STARTED,
            message=f"{self._identity.agent_id} starting task",
        )
        result = await self.execute_task(request)
        yield TaskProgress(
            task_id=request.id,
            kind=TaskProgressKind.RESULT,
            message=f"{self._identity.agent_id} finished task",
            result=result,
        )

    async def cancel_task(self, task_id: str, reason: str) -> None:
        """Cooperatively cancel. Idempotent."""
        self._cancellation_requested.add(task_id)
        _log.info(
            "agent.cancel_requested",
            agent_id=self._identity.agent_id,
            task_id=task_id,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Health & metrics
    # ------------------------------------------------------------------

    async def report_health(self) -> HealthReport:
        """Return current health."""
        if not self._initialized:
            return HealthReport.unhealthy("not initialized")
        return self._health

    async def report_metrics(self) -> MetricsReport:
        """Return operational metrics."""
        latencies = list(self._latencies)
        avg = sum(latencies) / len(latencies) if latencies else 0.0
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)
        return MetricsReport(
            agent_id=self._identity.agent_id,
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            tasks_cancelled=self._tasks_cancelled,
            avg_latency_ms=avg,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            tokens_consumed=self._tokens_consumed,
            cost_usd=self._cost_usd,
        )

    @staticmethod
    def _percentile(values: list[float], pct: int) -> float:
        """Compute the pct-th percentile of a list of values."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (pct / 100.0)
        f = int(k)
        c = min(f + 1, len(sorted_vals) - 1)
        if f == c:
            return sorted_vals[f]
        return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    async def request_permission(self, request: PermissionRequest) -> PermissionDecision:
        """Forward a permission request to the context's permission manager.

        Subclasses may override to add caching or batching.
        """
        if self._context is None:
            return PermissionDecision.DENY
        # Phase 4: the context doesn't yet carry a permission manager (that's
        # the Security Layer, Phase 8). Default to ALLOW for in-process agents.
        # The Gateway's permission checker (Phase 3) is the real gate.
        return PermissionDecision.ALLOW

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    async def serialize_state(self) -> AgentState:
        """Default: empty state. Subclasses override to add real state."""
        return AgentState(agent_id=self._identity.agent_id, format="1", data={})

    async def restore_state(self, state: AgentState) -> None:
        """Default: no-op (empty state). Subclasses override to restore real state."""
        if state.agent_id != self._identity.agent_id:
            from core.contracts.agent import StateIncompatibleError

            raise StateIncompatibleError(
                self._identity.agent_id,
                self._identity.agent_id,
                state.agent_id,
            )
        # Default: accept but ignore the data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_health(
        self, state: HealthState, reason: str = "", failing: list[str] | None = None
    ) -> None:
        """Update this agent's health (for subclasses)."""
        if state == HealthState.HEALTHY:
            self._health = HealthReport.healthy()
        elif state == HealthState.DEGRADED:
            self._health = HealthReport.degraded(reason, failing)
        else:
            self._health = HealthReport.unhealthy(reason, failing)

    async def _emit_event(
        self,
        topic: EventTopic,
        request: TaskRequest,
        detail: str = "",
    ) -> None:
        """Emit an event on the bus (if available)."""
        if self._context is None or self._context.bus is None:
            return
        bus = self._context.bus
        payload: dict[str, Any] = {
            "agent_id": self._identity.agent_id,
            "task_id": str(request.id),
        }
        if detail:
            payload["detail"] = detail
        await bus.publish(
            Event(
                topic=topic,
                correlation_id=request.id,
                actor=self._context.metadata.get("actor") if self._context.metadata else None,  # type: ignore[arg-type]
                payload=payload,
            ),
        )
