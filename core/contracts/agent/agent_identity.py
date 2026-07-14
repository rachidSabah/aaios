"""Agent identity and type taxonomy.

The 16 agent types defined here are the canonical taxonomy. Every agent
implementation declares one of these types in its ``AgentIdentity``. The
Supervisor's Capability Selector never uses the type for dispatch — it uses
the ``CapabilityManifest`` — but the type is used for:

  - Dashboard grouping ("show me all CodingAgents")
  - Type-specific Protocols (``CodingAgent`` extends ``GenericAgent`` with
    type-specific methods)
  - Permission catalog (e.g. "only DesktopAgents may request
    ``gateway.desktop.input``")
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AgentType(StrEnum):
    """The 16 canonical agent types.

    New types cannot be added without an architecture change (rare).
    Plugins that need a type outside this taxonomy use ``CUSTOM``.
    """

    SUPERVISOR = "supervisor"
    PLANNER = "planner"
    CODING = "coding"
    DESKTOP = "desktop"
    RESEARCH = "research"
    BROWSER = "browser"
    MEMORY = "memory"
    REFLECTION = "reflection"
    QA = "qa"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    VISION = "vision"
    VOICE = "voice"
    DOCUMENT = "document"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class AgentIdentity(BaseModel):
    """Stable identity for an agent.

    The ``agent_id`` is unique within the registry. Convention:
    ``<implementation-name>-v<major>`` (e.g. ``mock-coding-v1``,
    ``<vendor>-<type>-v1`` for vendor-provided agents).

    The ``signature`` is the publisher's signature over the manifest
    (None for unsigned plugins — the user must opt in to install).
    """

    model_config = ConfigDict(frozen=True)

    agent_id: str = Field(description="Unique ID within the registry.")
    agent_type: AgentType
    implementation_name: str = Field(description='Display name, e.g. "Mock Coding Agent".')
    version: str = Field(description='Semver, e.g. "1.0.0".')
    vendor: str = Field(default="AAiOS", description="Publisher.")
    signature: str | None = Field(
        default=None, description="Publisher signature (None for unsigned)."
    )

    def __str__(self) -> str:
        """Compact form: ``mock-coding-v1 (CodingAgent v1.0.0 by AAiOS)``."""
        return f"{self.agent_id} ({self.agent_type.value.title()}Agent v{self.version} by {self.vendor})"
