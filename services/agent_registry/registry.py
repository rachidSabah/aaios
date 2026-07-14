"""Agent Registry implementation.

The registry is the single source of truth for "which agents exist and what
can they do." Capability-based, not name-based. The Supervisor's Capability
Selector queries this registry, never an agent's class or implementation name.

Key invariants:
  - The registry never leaks agent implementation details to callers. The
    ``AgentSummary`` returned by ``list()`` and ``find_by_capability()``
    contains only the agent_id, type, version, capabilities, health, and
    track record — never the instance.
  - The caller obtains the instance via ``get(agent_id)`` only when it's
    about to dispatch a task. The registry does not pre-dispatch.
  - Hot-reload preserves in-flight tasks: the new instance is initialized
    in parallel with the old; the old is given a graceful shutdown with a
    60-second timeout; only then is it removed from the registry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from core.contracts.agent import (
    AgentContext,
    AgentIdentity,
    CapabilityManifest,
)
from core.contracts.health import HealthReport, HealthState
from core.logging import get_logger
from services.agent_registry.exceptions import (
    AgentAlreadyRegisteredError,
    AgentInitError,
    AgentNotFoundError,
    CircularDependencyError,
)

_log = get_logger(__name__)


class AgentProtocol(Protocol):
    """The minimal interface the registry needs from an agent.

    This is a structural type — any class implementing ``GenericAgent``
    (see ``agents/_types/gen.py``) satisfies it.
    """

    @property
    def identity(self) -> AgentIdentity: ...

    async def initialize(self, context: AgentContext) -> None: ...

    async def shutdown(self, graceful: bool = True) -> None: ...

    async def discover_capabilities(self) -> CapabilityManifest: ...

    async def report_health(self) -> HealthReport: ...


class AgentSummaryHealth(StrEnum):
    """Public-facing health state (mirrors HealthState but with an extra UNKNOWN)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class AgentSummary:
    """A public summary of a registered agent.

    Returned by ``list()`` and ``find_by_capability()``. Does NOT contain
    the agent instance — callers must use ``get(agent_id)`` to obtain it.
    """

    agent_id: str
    agent_type: str
    implementation_name: str
    version: str
    vendor: str
    capabilities: list[str]
    health: AgentSummaryHealth
    enabled: bool
    initialized: bool
    track_record: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_manifest(
        cls,
        manifest: CapabilityManifest,
        *,
        health: AgentSummaryHealth = AgentSummaryHealth.UNKNOWN,
        enabled: bool = True,
        initialized: bool = False,
        track_record: dict[str, float] | None = None,
    ) -> AgentSummary:
        """Build a summary from a capability manifest."""
        return cls(
            agent_id=manifest.identity.agent_id,
            agent_type=manifest.identity.agent_type.value,
            implementation_name=manifest.identity.implementation_name,
            version=manifest.identity.version,
            vendor=manifest.identity.vendor,
            capabilities=manifest.capability_namespaces(),
            health=health,
            enabled=enabled,
            initialized=initialized,
            track_record=track_record or {},
        )


@dataclass
class AgentFilter:
    """Filter for ``AgentRegistry.list()``."""

    agent_type: str | None = None
    capability: str | None = None
    health: AgentSummaryHealth | None = None
    enabled: bool | None = None
    initialized: bool | None = None


@dataclass
class _RegistryEntry:
    """Internal registry entry. Holds the instance + manifest + health."""

    agent: AgentProtocol
    manifest: CapabilityManifest
    health: HealthReport
    enabled: bool = True
    initialized: bool = False
    # Track record: { 'success_rate': 0.95, 'avg_latency_ms': 1200, 'cost_usd': 0.12 }
    track_record: dict[str, float] = field(default_factory=dict)
    # Dependencies: agent_ids this agent depends on
    dependencies: set[str] = field(default_factory=set)


class AgentRegistry:
    """The Agent Registry.

    Use ``init_agent_registry()`` to create one and ``get_agent_registry()``
    to retrieve it.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _RegistryEntry] = {}
        self._by_capability: dict[str, set[str]] = {}  # cap -> {agent_id}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_interval_s: float = 10.0
        self._default_context: AgentContext | None = None

    def set_default_context(self, context: AgentContext) -> None:
        """Set the default AgentContext used to initialize new agents."""
        self._default_context = context

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        agent: AgentProtocol,
        *,
        initialize: bool = True,
        dependencies: list[str] | None = None,
    ) -> str:
        """Register an agent.

        Args:
            agent: the agent instance (must satisfy AgentProtocol).
            initialize: if True (default), call ``agent.initialize(context)``
                and ``agent.discover_capabilities()`` before storing. If
                False, the agent is registered but not yet usable.
            dependencies: agent_ids this agent depends on. The registry
                will refuse to register if a dependency is missing or if
                adding the dependency would create a cycle.

        Returns:
            The agent_id of the newly registered agent.

        Raises:
            AgentAlreadyRegisteredError: if the agent_id is already registered.
            AgentInitError: if initialize=True and the agent fails to init.
            CircularDependencyError: if dependencies form a cycle.
        """
        agent_id = agent.identity.agent_id
        async with self._lock:
            if agent_id in self._entries:
                raise AgentAlreadyRegisteredError(agent_id)

            # Dependency check
            deps = set(dependencies or [])
            for dep in deps:
                if dep not in self._entries:
                    raise AgentNotFoundError(
                        f"Dependency {dep!r} not registered (required by {agent_id!r}).",
                    )
            # Cycle check
            self._check_no_cycle(agent_id, deps)

            manifest: CapabilityManifest | None = None
            initialized = False
            health = HealthReport.unhealthy("not initialized")

            if initialize:
                if self._default_context is None:
                    raise AgentInitError(
                        agent_id,
                        "No default AgentContext set. Call set_default_context() first.",
                    )
                try:
                    await agent.initialize(self._default_context)
                    manifest = await agent.discover_capabilities()
                    health = await agent.report_health()
                    initialized = True
                except Exception as e:
                    raise AgentInitError(agent_id, str(e)) from e
            else:
                # Even without initialize, we need a manifest for indexing
                # Try to call discover_capabilities; if it fails, store without
                try:
                    manifest = await agent.discover_capabilities()
                except Exception:
                    manifest = None

            entry = _RegistryEntry(
                agent=agent,
                manifest=manifest or CapabilityManifest(identity=agent.identity),
                health=health,
                enabled=True,
                initialized=initialized,
                track_record={},
                dependencies=deps,
            )
            self._entries[agent_id] = entry
            if manifest is not None:
                self._index_capabilities(agent_id, manifest)

            _log.info(
                "agent_registry.registered",
                agent_id=agent_id,
                agent_type=agent.identity.agent_type.value,
                capabilities=manifest.capability_namespaces() if manifest else [],
                initialized=initialized,
            )
            return agent_id

    async def unregister(self, agent_id: str) -> bool:
        """Unregister an agent. Graceful shutdown.

        Returns True if the agent was present (and is now removed).
        """
        async with self._lock:
            entry = self._entries.pop(agent_id, None)
            if entry is None:
                return False
            # Remove from capability index
            for cap in entry.manifest.capability_namespaces():
                if cap in self._by_capability:
                    self._by_capability[cap].discard(agent_id)
                    if not self._by_capability[cap]:
                        del self._by_capability[cap]
            # Graceful shutdown
            try:
                await entry.agent.shutdown(graceful=True)
            except Exception:
                _log.exception("agent_registry.unregister_shutdown_failed", agent_id=agent_id)
            _log.info("agent_registry.unregistered", agent_id=agent_id)
            return True

    async def enable(self, agent_id: str) -> None:
        """Enable an agent (allow dispatch)."""
        async with self._lock:
            entry = self._entries.get(agent_id)
            if entry is None:
                raise AgentNotFoundError(agent_id)
            entry.enabled = True
            _log.info("agent_registry.enabled", agent_id=agent_id)

    async def disable(self, agent_id: str) -> None:
        """Disable an agent (no new dispatch, but in-flight tasks continue)."""
        async with self._lock:
            entry = self._entries.get(agent_id)
            if entry is None:
                raise AgentNotFoundError(agent_id)
            entry.enabled = False
            _log.info("agent_registry.disabled", agent_id=agent_id)

    async def reload(self, agent_id: str) -> None:
        """Hot-reload an agent. Initializes a new instance in parallel with
        the old; once healthy, the old is shut down gracefully.

        Phase 4 stub: the actual hot-reload (which requires loading the new
        code) lands in Phase 11 with the Plugin Manager. Here, we just
        re-initialize the existing instance.
        """
        async with self._lock:
            entry = self._entries.get(agent_id)
            if entry is None:
                raise AgentNotFoundError(agent_id)
            try:
                if self._default_context is not None:
                    await entry.agent.initialize(self._default_context)
                    entry.manifest = await entry.agent.discover_capabilities()
                    entry.health = await entry.agent.report_health()
                    entry.initialized = True
                # Re-index capabilities
                for cap in entry.manifest.capability_namespaces():
                    self._by_capability.setdefault(cap, set()).add(agent_id)
                _log.info("agent_registry.reloaded", agent_id=agent_id)
            except Exception as e:
                _log.exception("agent_registry.reload_failed", agent_id=agent_id)
                raise AgentInitError(agent_id, str(e)) from e

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> AgentProtocol:
        """Return the agent instance (for dispatch)."""
        entry = self._entries.get(agent_id)
        if entry is None:
            raise AgentNotFoundError(agent_id)
        return entry.agent

    def list_agents(self, filter: AgentFilter | None = None) -> list[AgentSummary]:
        """Return summaries of all agents (optionally filtered)."""
        result: list[AgentSummary] = []
        for entry in self._entries.values():
            summary = AgentSummary.from_manifest(
                entry.manifest,
                health=self._public_health(entry),
                enabled=entry.enabled,
                initialized=entry.initialized,
                track_record=dict(entry.track_record),
            )
            if self._matches_filter(summary, filter):
                result.append(summary)
        return sorted(result, key=lambda s: s.agent_id)

    def find_by_capability(self, capability: str) -> list[AgentSummary]:
        """Return all enabled, healthy agents that advertise ``capability``."""
        agent_ids = self._by_capability.get(capability, set())
        result: list[AgentSummary] = []
        for agent_id in agent_ids:
            entry = self._entries.get(agent_id)
            if entry is None or not entry.enabled:
                continue
            summary = AgentSummary.from_manifest(
                entry.manifest,
                health=self._public_health(entry),
                enabled=entry.enabled,
                initialized=entry.initialized,
                track_record=dict(entry.track_record),
            )
            result.append(summary)
        return sorted(result, key=lambda s: s.agent_id)

    def has(self, agent_id: str) -> bool:
        """Return True if the agent is registered."""
        return agent_id in self._entries

    def get_manifest(self, agent_id: str) -> CapabilityManifest:
        """Return the capability manifest for an agent."""
        entry = self._entries.get(agent_id)
        if entry is None:
            raise AgentNotFoundError(agent_id)
        return entry.manifest

    def get_track_record(self, agent_id: str) -> dict[str, float]:
        """Return the track record for an agent."""
        entry = self._entries.get(agent_id)
        if entry is None:
            raise AgentNotFoundError(agent_id)
        return dict(entry.track_record)

    def update_track_record(self, agent_id: str, metrics: dict[str, float]) -> None:
        """Update the track record for an agent."""
        entry = self._entries.get(agent_id)
        if entry is None:
            raise AgentNotFoundError(agent_id)
        entry.track_record.update(metrics)

    def list_capabilities(self) -> list[str]:
        """Return all capability namespaces indexed by the registry."""
        return sorted(self._by_capability.keys())

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def heartbeat(self) -> dict[str, AgentSummaryHealth]:
        """Call report_health on every agent. Update internal state.

        Returns a map of agent_id -> public health state.
        """
        result: dict[str, AgentSummaryHealth] = {}
        for agent_id, entry in list(self._entries.items()):
            if not entry.initialized:
                result[agent_id] = AgentSummaryHealth.UNKNOWN
                continue
            try:
                health = await asyncio.wait_for(
                    entry.agent.report_health(),
                    timeout=5.0,
                )
                entry.health = health
                result[agent_id] = self._public_health(entry)
            except TimeoutError:
                entry.health = HealthReport.unhealthy("health check timeout")
                result[agent_id] = AgentSummaryHealth.UNHEALTHY
            except Exception:
                entry.health = HealthReport.unhealthy("health check failed")
                result[agent_id] = AgentSummaryHealth.UNHEALTHY
        return result

    async def start_heartbeat(self, interval_s: float = 10.0) -> None:
        """Start the background heartbeat task."""
        self._heartbeat_interval_s = interval_s
        if self._heartbeat_task is not None:
            return
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name="agent_registry.heartbeat",
        )

    async def stop_heartbeat(self) -> None:
        """Stop the background heartbeat task."""
        if self._heartbeat_task is None:
            return
        self._heartbeat_task.cancel()
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass
        self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """Background loop: call heartbeat() on a schedule."""
        while True:
            try:
                await self.heartbeat()
            except Exception:
                _log.exception("agent_registry.heartbeat_failed")
            await asyncio.sleep(self._heartbeat_interval_s)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Shut down all agents and stop the heartbeat."""
        await self.stop_heartbeat()
        for agent_id in list(self._entries.keys()):
            await self.unregister(agent_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _index_capabilities(self, agent_id: str, manifest: CapabilityManifest) -> None:
        """Index an agent's capabilities for O(1) lookup."""
        for cap in manifest.capability_namespaces():
            self._by_capability.setdefault(cap, set()).add(agent_id)

    def _check_no_cycle(self, agent_id: str, dependencies: set[str]) -> None:
        """Check that adding ``agent_id -> dependencies`` doesn't create a cycle.

        A cycle exists if, starting from any of ``dependencies`` and walking
        the existing dependency graph, we arrive back at ``agent_id``.
        """
        visited: set[str] = set()
        path: list[str] = []

        def visit(node: str) -> None:
            # Cycle back to the starting agent_id
            if node == agent_id and path:
                cycle = path + [node]
                raise CircularDependencyError(cycle)
            # Self-dependency
            if node == agent_id and not path:
                raise CircularDependencyError([agent_id, agent_id])
            # Cycle within the existing graph (not involving agent_id)
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                raise CircularDependencyError(cycle)
            if node in visited:
                return
            path.append(node)
            entry = self._entries.get(node)
            if entry is not None:
                for dep in entry.dependencies:
                    visit(dep)
            path.pop()
            visited.add(node)

        for dep in dependencies:
            visit(dep)

    @staticmethod
    def _public_health(entry: _RegistryEntry) -> AgentSummaryHealth:
        """Map internal HealthReport to public AgentSummaryHealth."""
        if not entry.initialized:
            return AgentSummaryHealth.UNKNOWN
        if entry.health.state == HealthState.HEALTHY:
            return AgentSummaryHealth.HEALTHY
        if entry.health.state == HealthState.DEGRADED:
            return AgentSummaryHealth.DEGRADED
        return AgentSummaryHealth.UNHEALTHY

    @staticmethod
    def _matches_filter(summary: AgentSummary, filter: AgentFilter | None) -> bool:
        """Return True if summary matches the filter."""
        if filter is None:
            return True
        if filter.agent_type is not None and summary.agent_type != filter.agent_type:
            return False
        if filter.capability is not None and filter.capability not in summary.capabilities:
            return False
        if filter.health is not None and summary.health != filter.health:
            return False
        if filter.enabled is not None and summary.enabled != filter.enabled:
            return False
        if filter.initialized is not None and summary.initialized != filter.initialized:
            return False
        return True


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_INSTANCE: AgentRegistry | None = None


def init_agent_registry() -> AgentRegistry:
    """Initialize the global Agent Registry."""
    global _INSTANCE
    _INSTANCE = AgentRegistry()
    return _INSTANCE


def get_agent_registry() -> AgentRegistry:
    """Return the global Agent Registry."""
    if _INSTANCE is None:
        raise RuntimeError("AgentRegistry not initialized. Call init_agent_registry() first.")
    return _INSTANCE


def set_agent_registry(registry: AgentRegistry) -> None:
    """Set the global Agent Registry (for testing)."""
    global _INSTANCE
    _INSTANCE = registry
