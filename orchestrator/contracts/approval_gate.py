"""Approval gate — declares that a step requires human approval.

Any step can declare an approval gate. When the Orchestrator reaches the
gate, it emits ``approval.requested``, the Permission Manager surfaces it
to the user, and execution pauses until the user responds.

If ``on_timeout=pause``, the task is paused and the user is notified.
If ``on_timeout=deny``, the step fails.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ApprovalGate", "GateType", "GateTimeoutAction"]


class GateType(StrEnum):
    """When in the step lifecycle the gate fires."""

    PRE_STEP = "pre_step"  # before the step starts
    POST_STEP = "post_step"  # after the step completes, before commit
    PRE_COMMIT = "pre_commit"  # right before committing the checkpoint


class GateTimeoutAction(StrEnum):
    """What to do if the approval times out."""

    PAUSE = "pause"  # pause the task, notify the user
    DENY = "deny"  # fail the step


class ApprovalGate(BaseModel):
    """A human approval gate on a step."""

    model_config = ConfigDict(frozen=True)

    gate_type: GateType = Field(default=GateType.PRE_STEP)
    required_role: str = Field(default="operator", description="owner | admin | operator")
    timeout_s: int = Field(default=300, ge=1, description="5 min default")
    on_timeout: GateTimeoutAction = Field(default=GateTimeoutAction.PAUSE)
    message: str = Field(default="", description="Shown to the user in the approval UI.")
    # Optional: a schema the user must satisfy (e.g. confirm a file path)
    confirmation_schema: dict[str, Any] | None = Field(default=None)
