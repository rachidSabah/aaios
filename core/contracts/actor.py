"""Actor references — the identity model used in events, audit, and permissions."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ActorType(StrEnum):
    """The kind of actor that initiated an action."""

    USER = "user"
    AGENT = "agent"
    PLUGIN = "plugin"
    MCP_SERVER = "mcp_server"
    SYSTEM = "system"


class ActorRef(BaseModel):
    """A stable reference to the actor behind an event or action.

    Actors include users (via OAuth or API key), agents (via the supervisor),
    plugins, MCP servers, and the system itself (boot, scheduled tasks).
    """

    type: ActorType
    id: str = Field(description="Stable identifier within the type namespace.")
    display_name: str = Field(default="", description="Human-readable name.")
    instance_id: UUID = Field(
        default_factory=uuid4,
        description="Per-process instance ID; differs across restarts.",
    )

    def __str__(self) -> str:
        """Compact string form: ``user:alice`` / ``agent:<id>``."""
        return f"{self.type}:{self.id}"

    @classmethod
    def system(cls) -> ActorRef:
        """Return the canonical 'system' actor — used for boot, scheduled tasks, etc."""
        return cls(type=ActorType.SYSTEM, id="system", display_name="AAiOS System")

    @classmethod
    def user(cls, user_id: str, display_name: str = "") -> ActorRef:
        """Return a user actor."""
        return cls(type=ActorType.USER, id=user_id, display_name=display_name or user_id)

    @classmethod
    def agent(cls, agent_id: str, display_name: str = "") -> ActorRef:
        """Return an agent actor."""
        return cls(type=ActorType.AGENT, id=agent_id, display_name=display_name or agent_id)

    @classmethod
    def plugin(cls, plugin_id: str, display_name: str = "") -> ActorRef:
        """Return a plugin actor."""
        return cls(type=ActorType.PLUGIN, id=plugin_id, display_name=display_name or plugin_id)
