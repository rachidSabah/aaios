"""Permission contracts — used by the Security Layer and Permission Manager."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from core.contracts.actor import ActorRef
from core.contracts.timestamp import utc_now


class PermissionDecision(StrEnum):
    """The outcome of a permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Permission(BaseModel):
    """A typed permission descriptor.

    Permissions are dot-separated namespaces (e.g. ``gateway.fs.read``,
    ``tool.call.slack.send_message``, ``agent.dispatch``). The Security
    Layer matches these against the policy table.
    """

    name: str = Field(description="Dot-separated permission name.")
    resource: str = Field(
        default="*",
        description="Resource specifier (path, host, tool ID, etc.).",
    )
    constraints: dict[str, str] = Field(
        default_factory=dict,
        description="Additional constraints (e.g. scope=project-A).",
    )

    def __str__(self) -> str:
        """Compact string form."""
        if self.resource == "*":
            return self.name
        return f"{self.name}({self.resource})"


class PermissionRequest(BaseModel):
    """A request to perform an action that requires permission.

    This is what an agent (or any L3 component) sends to the Security Layer.
    If the policy returns ``ASK``, the Security Layer forwards a
    PermissionRequest to the Permission Manager for interactive approval.
    """

    actor: ActorRef = Field(description="Who is requesting the permission.")
    permission: Permission
    description: str = Field(default="", description="Human-readable explanation for the UI.")
    requested_at: datetime = Field(default_factory=utc_now)
    task_correlation_id: str | None = Field(
        default=None,
        description="The task this request is in service of, if any.",
    )


__all__ = ["Permission", "PermissionDecision", "PermissionRequest"]
