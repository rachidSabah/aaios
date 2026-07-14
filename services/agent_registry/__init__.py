"""Agent Registry — the single source of truth for "which agents exist
and what can they do."

Capability-based, not name-based. The Capability Selector queries this
registry, never an agent's class or implementation name.

Responsibilities (from the architecture):
  - Discovery: at boot, scan for GenericAgent implementations (entry points +
    plugin manifests). Instantiate, initialize, discover_capabilities, store.
  - Indexing: maintain ``capability -> [agent_id]`` for O(1) lookups.
  - Health monitoring: call report_health on each agent on a heartbeat
    schedule (default 10s). Mark degraded/unhealthy based on response or
    timeout.
  - Lifecycle: enable, disable, reload (hot-reload preserves in-flight tasks),
    uninstall.
  - Versioning: multiple versions of the same agent can coexist.
  - Dependency resolution: agents can declare dependencies on other agents.
  - Capability indexing: every capability namespace is indexed. Reserved
    namespaces are validated against the type taxonomy.
"""

from __future__ import annotations

from services.agent_registry.exceptions import (
    AgentAlreadyRegisteredError,
    AgentInitError,
    AgentNotFoundError,
    CircularDependencyError,
)
from services.agent_registry.registry import (
    AgentFilter,
    AgentRegistry,
    AgentSummary,
    AgentSummaryHealth,
    get_agent_registry,
    init_agent_registry,
    set_agent_registry,
)

__all__ = [
    "AgentAlreadyRegisteredError",
    "AgentFilter",
    "AgentInitError",
    "AgentNotFoundError",
    "AgentRegistry",
    "AgentSummary",
    "AgentSummaryHealth",
    "CircularDependencyError",
    "get_agent_registry",
    "init_agent_registry",
    "set_agent_registry",
]
