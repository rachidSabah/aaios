"""The GenericAgent Protocol — the 11-method interface every agent implements.

This is the architectural centerpiece. No code outside ``agents/_impls/<name>/``
references a specific agent implementation by name (INV-09). The Supervisor,
Task Orchestrator, Memory, Security, and Dashboard all work against this
interface and the ``CapabilityManifest`` it exposes.

See ``docs/architecture/02-generic-agent-runtime.md`` for the full spec.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from core.contracts.agent import AgentContext, AgentIdentity, AgentState, MetricsReport
from core.contracts.health import HealthReport
from core.contracts.permission import PermissionDecision, PermissionRequest
from core.contracts.task import TaskProgress, TaskRequest, TaskResult


@runtime_checkable
class GenericAgent(Protocol):
    """The contract every AAiOS agent must satisfy.

    All 11 methods are documented below. Implementations may be:
      - In-process Python classes (in ``agents/_impls/``)
      - Subprocess bridges (wrapping external CLIs like Claude Code)
      - Remote services (HTTP/gRPC to a separate agent process)

    The Supervisor does not know which style an agent uses. The Agent
    Registry does, and uses it for health-check strategy and resource
    accounting, but never leaks this detail to the Supervisor.

    Design rules (from the architecture doc):
      1. All methods are async. No blocking I/O.
      2. All arguments and returns are Pydantic models. No bare dicts.
      3. ``initialize``, ``shutdown``, ``cancel_task`` are idempotent.
      4. Every method has a configurable timeout (enforced at the Supervisor level).
      5. Methods must not log secret material.
      6. ``execute_task`` and ``stream_progress`` emit at least
         ``agent.task.started`` and ``agent.task.finished`` events.
    """

    # ------------------------------------------------------------------
    # Identity & lifecycle (3 methods)
    # ------------------------------------------------------------------

    @property
    def identity(self) -> AgentIdentity:
        """Stable identity: agent_id, agent_type, version, vendor, signature."""
        ...

    async def initialize(self, context: AgentContext) -> None:
        """Called once at agent boot.

        Acquire resources, open connections, verify environment, register
        with the Agent Registry. Must be idempotent — calling initialize on
        an already-initialized agent is a no-op. Raises ``AgentInitError``
        on failure; the registry will mark the agent unhealthy and not
        route tasks to it.
        """
        ...

    async def shutdown(self, graceful: bool = True) -> None:
        """Release all resources.

        If ``graceful=True``, finish in-flight tasks (up to a timeout)
        before exiting. If ``graceful=False``, abort immediately (used on
        catastrophic failure or system shutdown). Must not raise —
        shutdown errors are logged but never propagated.
        """
        ...

    # ------------------------------------------------------------------
    # Capability discovery (1 method)
    # ------------------------------------------------------------------

    async def discover_capabilities(self) -> Any:  # returns CapabilityManifest
        """Return the agent's capability manifest.

        Called by the Agent Registry at registration time and on hot-reload.
        The manifest is the ONLY mechanism by which the Supervisor learns
        what an agent can do. Agents must NOT advertise capabilities they
        do not actually implement — the QA Agent will detect mismatches.
        """
        ...

    # ------------------------------------------------------------------
    # Task execution (3 methods)
    # ------------------------------------------------------------------

    async def execute_task(self, request: TaskRequest) -> TaskResult:
        """Execute a single task synchronously (from the caller's POV).

        Internally the agent is free to spawn subtasks, call models, etc.
        Returns the final ``TaskResult``. May raise ``TaskFailedError`` or
        ``TaskCancelledError``. Long-running tasks should use
        ``stream_progress`` instead.
        """
        ...

    def stream_progress(self, request: TaskRequest) -> AsyncIterator[TaskProgress]:
        """Async iterator yielding progress events as the task runs.

        The final yield is a ``TaskProgress`` with ``kind='result'`` carrying
        the ``TaskResult``. Used by the Supervisor for long-running tasks so
        the dashboard can show live progress. Agents that don't have
        meaningful intermediate progress may just yield the result.
        """
        ...

    async def cancel_task(self, task_id: str, reason: str) -> None:
        """Cooperatively cancel an in-flight task.

        The agent should stop work as soon as it reaches a safe checkpoint,
        clean up partial state, and raise ``TaskCancelledError`` from
        ``execute_task`` / ``stream_progress``. Must be idempotent —
        cancelling an already-cancelled or completed task is a no-op.
        Cancellation must be fast (target: <2 seconds) but safe (no
        corrupted state).
        """
        ...

    # ------------------------------------------------------------------
    # Health & metrics (2 methods)
    # ------------------------------------------------------------------

    async def report_health(self) -> HealthReport:
        """Return current health.

        ``healthy`` | ``degraded`` | ``unhealthy``, plus a human-readable
        reason and a list of failing subsystems. Called by the registry on
        a heartbeat schedule (default 10s) and on-demand by the Supervisor
        before dispatch.
        """
        ...

    async def report_metrics(self) -> MetricsReport:
        """Return operational metrics.

        ``tasks_completed``, ``tasks_failed``, ``avg_latency_ms``,
        ``p95_latency_ms``, ``tokens_consumed``, ``cost_usd``,
        ``custom_metrics``. Used by the Telemetry service and the
        dashboard's per-agent analytics.
        """
        ...

    # ------------------------------------------------------------------
    # Permissions (1 method)
    # ------------------------------------------------------------------

    async def request_permission(self, request: PermissionRequest) -> PermissionDecision:
        """Ask the user (via the Permission Manager) for approval.

        The agent calls this BEFORE performing the action — never after.
        The Permission Manager surfaces the request to the user and returns
        the decision. Agents must respect denials without retry.
        """
        ...

    # ------------------------------------------------------------------
    # State persistence — for checkpointing & migration (2 methods)
    # ------------------------------------------------------------------

    async def serialize_state(self) -> AgentState:
        """Return a serializable snapshot of the agent's internal state.

        Used for: (a) checkpointing long tasks, (b) migrating an agent
        between hosts, (c) crash recovery. Must be deterministic — two
        calls in the same state return equal snapshots. Must not contain
        secret material (use SecretRef placeholders).
        """
        ...

    async def restore_state(self, state: AgentState) -> None:
        """Restore a previously serialized state.

        Called after a crash or migration. The agent must verify the state
        is compatible with its current version; if not, raise
        ``StateIncompatibleError`` and the registry will start the agent
        fresh.
        """
        ...


# Type alias for the CapabilityManifest return type of discover_capabilities()
# (Imported lazily to avoid a circular import in the Protocol definition.)
from typing import Any  # noqa: E402  # noqa: E402

__all__ = ["GenericAgent"]
