"""Capability manifest — the ONLY mechanism by which the Supervisor learns
what an agent can do.

Every agent returns a ``CapabilityManifest`` from ``discover_capabilities()``.
The Agent Registry indexes it by capability namespace. The Supervisor's
Capability Selector queries the registry to find agents for a step.

INV-09 enforcement: the manifest references capabilities (e.g.
``code.read``), never agent implementation names.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.agent.agent_identity import AgentIdentity
from core.contracts.permission import Permission


class SideEffect(BaseModel):
    """A declared side effect of a capability."""

    model_config = ConfigDict(frozen=True)

    kind: str = Field(
        description="fs.read | fs.write | net.request | shell.exec | memory.write | process.spawn | desktop.input | clipboard.*"
    )
    scope: str = Field(default="*", description="e.g. a path prefix, a host, a memory scope.")


class CostEstimate(BaseModel):
    """Rough cost estimate per invocation of a capability."""

    model_config = ConfigDict(frozen=True)

    avg_usd: float = Field(default=0.0, ge=0.0)
    avg_latency_s: float = Field(default=0.0, ge=0.0)
    avg_tokens: int = Field(default=0, ge=0)
    notes: str = Field(default="")


class CostModel(BaseModel):
    """How to estimate the cost of a task handled by this agent."""

    model_config = ConfigDict(frozen=True)

    fixed_usd: float = Field(default=0.0, ge=0.0, description="Cost per task regardless of size.")
    per_token_usd: float = Field(default=0.0, ge=0.0, description="Cost per LLM token consumed.")
    per_second_usd: float = Field(default=0.0, ge=0.0, description="Cost per second of execution.")


class HealthCheckSpec(BaseModel):
    """How the registry should probe this agent's health."""

    model_config = ConfigDict(frozen=True)

    interval_s: int = Field(default=10, ge=1)
    timeout_s: int = Field(default=2, ge=1)
    unhealthy_threshold: int = Field(
        default=3, ge=1, description="Consecutive failures to mark unhealthy."
    )
    degraded_threshold: int = Field(
        default=1, ge=1, description="Consecutive failures to mark degraded."
    )


class ResourceRequirements(BaseModel):
    """The resources an agent needs to run."""

    model_config = ConfigDict(frozen=True)

    cpu_cores: float = Field(default=0.5, ge=0.0)
    memory_mb: int = Field(default=128, ge=0)
    disk_mb: int = Field(default=0, ge=0)
    gpu: bool = Field(default=False)
    network: bool = Field(default=True)


class TimeoutDefaults(BaseModel):
    """Default timeouts per operation."""

    model_config = ConfigDict(frozen=True)

    initialize_s: float = Field(default=30.0, ge=0.0)
    discover_capabilities_s: float = Field(default=5.0, ge=0.0)
    execute_task_s: float = Field(default=300.0, ge=0.0)
    cancel_task_s: float = Field(default=2.0, ge=0.0)
    report_health_s: float = Field(default=2.0, ge=0.0)


class Capability(BaseModel):
    """A single capability an agent advertises."""

    model_config = ConfigDict(frozen=True)

    namespace: str = Field(description="Dot-separated, e.g. ``code.write``, ``desktop.ui.click``.")
    description: str = Field(default="")
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for inputs (used for LLM tool-calling).",
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema for outputs."
    )
    cost_estimate: CostEstimate = Field(default_factory=CostEstimate)
    requires_permission: Permission = Field(
        default_factory=lambda: Permission(name="tool.call"),
    )
    side_effects: list[SideEffect] = Field(default_factory=list)


class CapabilityManifest(BaseModel):
    """The full manifest an agent returns from ``discover_capabilities()``."""

    model_config = ConfigDict(frozen=True)

    identity: AgentIdentity
    capabilities: list[Capability] = Field(default_factory=list)
    resource_requirements: ResourceRequirements = Field(default_factory=ResourceRequirements)
    supported_models: list[str] | None = Field(
        default=None,
        description="None = uses Model Router choice; otherwise a list of model IDs.",
    )
    permissions_required: list[Permission] = Field(default_factory=list)
    config_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema for agent-specific config (under config.agents.<id>).",
    )
    health_check: HealthCheckSpec = Field(default_factory=HealthCheckSpec)
    timeout_defaults: TimeoutDefaults = Field(default_factory=TimeoutDefaults)
    cost_model: CostModel | None = Field(default=None)
    track_record_ref: str | None = Field(
        default=None,
        description="Memory scope reference for track record (success rate, latency, cost).",
    )

    def has_capability(self, namespace: str) -> bool:
        """Return True if the manifest advertises ``namespace``."""
        return any(c.namespace == namespace for c in self.capabilities)

    def capability_namespaces(self) -> list[str]:
        """Return all capability namespaces, sorted."""
        return sorted(c.namespace for c in self.capabilities)
