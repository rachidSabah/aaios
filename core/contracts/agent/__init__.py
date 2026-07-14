"""Agent contracts — identity, context, state, capability manifest, metrics.

These contracts are L1 (kernel) — they live in ``core/contracts/agent/``
because the Agent Registry (L2) and the Supervisor (L4) both need them, and
the kernel itself uses ``AgentContext`` for the SecretResolver hook.

Keeping them in ``core/contracts/`` enforces the layering: L2/L3/L4 import
from L1, never the reverse.
"""

from __future__ import annotations

from core.contracts.agent.agent_context import (
    AgentContext,
    AgentEnvironment,
    SecretResolver,
)
from core.contracts.agent.agent_identity import AgentIdentity, AgentType
from core.contracts.agent.agent_state import AgentState, StateIncompatibleError
from core.contracts.agent.capability_manifest import (
    Capability,
    CapabilityManifest,
    CostEstimate,
    CostModel,
    HealthCheckSpec,
    ResourceRequirements,
    SideEffect,
    TimeoutDefaults,
)
from core.contracts.agent.metrics import MetricsReport

__all__ = [
    "AgentContext",
    "AgentEnvironment",
    "AgentIdentity",
    "AgentState",
    "AgentType",
    "Capability",
    "CapabilityManifest",
    "CostEstimate",
    "CostModel",
    "HealthCheckSpec",
    "MetricsReport",
    "ResourceRequirements",
    "SecretResolver",
    "SideEffect",
    "StateIncompatibleError",
    "TimeoutDefaults",
]
