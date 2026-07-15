"""Mission state machine — manages lifecycle transitions with validation.

State diagram:

    created → planning → ready → executing ↔ paused
                ↑                   ↓
                └───────────────────┘ (replan)
                                    ↓
                          completed / failed / cancelled

Transitions are validated: only legal transitions are allowed, and each
transition emits an event on the mission event bus.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.organization.models import Mission, MissionStatus

_log = get_logger(__name__)

__all__ = [
    "IllegalTransitionError",
    "MissionStateTransition",
    "MissionStateMachine",
    "TRANSITION_EVENTS",
]


class IllegalTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


# Mapping of (from_state, to_state) → event topic
TRANSITION_EVENTS: dict[tuple[str, str], str] = {
    (MissionStatus.CREATED.value, MissionStatus.PLANNING.value): "mission.planning_started",
    (MissionStatus.PLANNING.value, MissionStatus.READY.value): "mission.ready",
    (MissionStatus.PLANNING.value, MissionStatus.PLANNING.value): "mission.replanned",
    (MissionStatus.READY.value, MissionStatus.EXECUTING.value): "mission.started",
    (MissionStatus.EXECUTING.value, MissionStatus.PAUSED.value): "mission.paused",
    (MissionStatus.PAUSED.value, MissionStatus.EXECUTING.value): "mission.resumed",
    (MissionStatus.EXECUTING.value, MissionStatus.COMPLETED.value): "mission.completed",
    (MissionStatus.EXECUTING.value, MissionStatus.FAILED.value): "mission.failed",
    (MissionStatus.EXECUTING.value, MissionStatus.PLANNING.value): "mission.replan",
    (MissionStatus.PAUSED.value, MissionStatus.PLANNING.value): "mission.replan",
    (MissionStatus.PAUSED.value, MissionStatus.CANCELLED.value): "mission.cancelled",
    (MissionStatus.EXECUTING.value, MissionStatus.CANCELLED.value): "mission.cancelled",
    (MissionStatus.READY.value, MissionStatus.CANCELLED.value): "mission.cancelled",
    (MissionStatus.PLANNING.value, MissionStatus.CANCELLED.value): "mission.cancelled",
    (MissionStatus.CREATED.value, MissionStatus.CANCELLED.value): "mission.cancelled",
    (MissionStatus.FAILED.value, MissionStatus.PLANNING.value): "mission.replan",
    (MissionStatus.PAUSED.value, MissionStatus.FAILED.value): "mission.failed",
}


# Valid transitions from each state
VALID_TRANSITIONS: dict[str, set[str]] = {
    MissionStatus.CREATED.value: {
        MissionStatus.PLANNING.value,
        MissionStatus.CANCELLED.value,
    },
    MissionStatus.PLANNING.value: {
        MissionStatus.READY.value,
        MissionStatus.PLANNING.value,  # replan
        MissionStatus.CANCELLED.value,
    },
    MissionStatus.READY.value: {
        MissionStatus.EXECUTING.value,
        MissionStatus.CANCELLED.value,
    },
    MissionStatus.EXECUTING.value: {
        MissionStatus.PAUSED.value,
        MissionStatus.COMPLETED.value,
        MissionStatus.FAILED.value,
        MissionStatus.PLANNING.value,  # replan
        MissionStatus.CANCELLED.value,
    },
    MissionStatus.PAUSED.value: {
        MissionStatus.EXECUTING.value,
        MissionStatus.PLANNING.value,  # replan
        MissionStatus.FAILED.value,
        MissionStatus.CANCELLED.value,
    },
    MissionStatus.COMPLETED.value: set(),  # terminal
    MissionStatus.FAILED.value: {
        MissionStatus.PLANNING.value,  # replan after failure
    },
    MissionStatus.CANCELLED.value: set(),  # terminal
}


class MissionStateTransition:
    """Record of a state transition."""

    def __init__(
        self,
        mission_id: str,
        from_state: str,
        to_state: str,
        event_topic: str,
        reason: str = "",
        actor: str = "system",
    ) -> None:
        self.mission_id = mission_id
        self.from_state = from_state
        self.to_state = to_state
        self.event_topic = event_topic
        self.reason = reason
        self.actor = actor

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "event_topic": self.event_topic,
            "reason": self.reason,
            "actor": self.actor,
        }


class MissionStateMachine:
    """Manages mission state transitions with validation.

    Usage:
        sm = MissionStateMachine()
        sm.transition(mission, MissionStatus.EXECUTING)
        events = sm.get_events_for_transition(mission.status, new_status)
    """

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Check if a transition is valid."""
        return to_state in VALID_TRANSITIONS.get(from_state, set())

    def get_event_topic(self, from_state: str, to_state: str) -> str | None:
        """Get the event topic for a transition, or None."""
        return TRANSITION_EVENTS.get((from_state, to_state))

    def transition(
        self,
        mission: Mission,
        to_state: str,
        *,
        reason: str = "",
        actor: str = "system",
    ) -> MissionStateTransition:
        """Transition a mission to a new state.

        Raises IllegalTransitionError if the transition is not valid.
        Returns the transition record (with event topic for publishing).
        """
        from_state = mission.status
        if not self.can_transition(from_state, to_state):
            raise IllegalTransitionError(
                f"Cannot transition mission {mission.mission_id} "
                f"from '{from_state}' to '{to_state}'",
            )
        event_topic = self.get_event_topic(from_state, to_state)
        if event_topic is None:
            # Same-state replan or unknown — use a generic event
            event_topic = "mission.state_changed"

        # Update mission timestamps
        from datetime import UTC, datetime
        mission.status = to_state
        mission.updated_at = datetime.now(UTC)
        if to_state == MissionStatus.EXECUTING.value and mission.started_at is None:
            mission.started_at = datetime.now(UTC)
        if to_state in (
            MissionStatus.COMPLETED.value,
            MissionStatus.FAILED.value,
            MissionStatus.CANCELLED.value,
        ):
            mission.completed_at = datetime.now(UTC)

        transition = MissionStateTransition(
            mission_id=mission.mission_id,
            from_state=from_state,
            to_state=to_state,
            event_topic=event_topic,
            reason=reason,
            actor=actor,
        )
        _log.info(
            "Mission %s transition: %s → %s (reason: %s, actor: %s)",
            mission.mission_id, from_state, to_state, reason, actor,
        )
        return transition

    def get_valid_transitions(self, state: str) -> set[str]:
        """Get all valid target states from the given state."""
        return VALID_TRANSITIONS.get(state, set())

    def is_terminal(self, state: str) -> bool:
        """Check if a state is terminal (no outgoing transitions)."""
        return len(VALID_TRANSITIONS.get(state, set())) == 0
