"""Agent state — for checkpointing, migration, and crash recovery.

``AgentState`` is the opaque snapshot returned by ``serialize_state()`` and
consumed by ``restore_state()``. The kernel does not interpret the state;
only the agent that produced it can restore it.

Rules (from the architecture doc):
  - Must be deterministic — two calls in the same state return equal snapshots.
  - Must not contain secret material (use SecretRef placeholders).
  - Must be serializable (Pydantic v2 BaseModel → JSON-safe).
  - Must declare a ``format`` version, so ``restore_state`` can detect
    incompatible snapshots and raise ``StateIncompatibleError``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StateIncompatibleError(RuntimeError):
    """Raised by ``restore_state()`` when the snapshot is incompatible."""

    def __init__(self, agent_id: str, current_format: str, snapshot_format: str) -> None:
        super().__init__(
            f"Agent {agent_id} cannot restore state: current format "
            f"{current_format!r} != snapshot format {snapshot_format!r}.",
        )
        self.agent_id = agent_id
        self.current_format = current_format
        self.snapshot_format = snapshot_format


class AgentState(BaseModel):
    """An opaque, serializable agent state snapshot.

    The ``data`` field is a free-form dict — agents put whatever they need
    there. The ``format`` field is the agent's own version of its state
    schema (independent of the agent's release version). If the agent's
    state schema changes in a backward-incompatible way, bump ``format``.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    format: str = Field(default="1", description="Agent-defined state schema version.")
    data: dict[str, Any] = Field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        """Equality is structural — two states are equal iff their data matches."""
        if not isinstance(other, AgentState):
            return NotImplemented
        return (
            self.agent_id == other.agent_id
            and self.format == other.format
            and self.data == other.data
        )

    def __hash__(self) -> int:
        """Hash by agent_id + format (data is mutable, not hashable)."""
        return hash((self.agent_id, self.format))
