"""State Manager — event-sourced state with snapshots.

The state manager holds in-memory caches of aggregate states, backed by the
event store (for the full log) and a snapshot store (for fast recovery).

On ``apply(event)``:
  1. The event is appended to the event store (via the bus).
  2. The matching reducer is invoked: ``new_state = reducer(current, event)``.
  3. The in-memory cache is updated.
  4. Every N events per aggregate, a snapshot is written.

On boot or recovery:
  1. Load the latest snapshot for each aggregate.
  2. Replay events from the snapshot's sequence number forward.
  3. Populate the in-memory cache.

Reducers are pure functions: ``(state, event) -> state``. They must not
perform I/O, must not raise (except for genuinely invalid events, which
will be logged and skipped — the state is not updated).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from core.contracts.event import Event
from core.event_bus import EventBus, get_bus
from core.logging import get_logger

_log = get_logger(__name__)

# Type aliases
AggregateId = UUID


class Aggregate(BaseModel):
    """Base class for aggregate state. Subclass to define specific aggregates."""

    id: AggregateId
    version: int = Field(default=0, description="Event count since creation.")


class Snapshot(BaseModel):
    """A point-in-time snapshot of an aggregate's state."""

    aggregate_id: AggregateId
    sequence: int
    state: Any
    taken_at: str  # ISO-8601


# Reducer signature: (current_state, event) -> new_state
Reducer = Callable[[Aggregate | None, Event], Aggregate | None]


class StateManager:
    """Event-sourced state manager.

    The state manager subscribes to the event bus on construction and
    applies every event to the matching reducer.
    """

    def __init__(
        self,
        bus: EventBus | None = None,
        *,
        snapshot_interval: int = 50,
    ) -> None:
        self._bus = bus or get_bus()
        self._reducers: dict[str, Reducer] = {}
        self._states: dict[AggregateId, Aggregate] = {}
        self._event_counts: dict[AggregateId, int] = defaultdict(int)
        self._snapshots: dict[AggregateId, Snapshot] = {}
        self._snapshot_interval = snapshot_interval
        self._lock = asyncio.Lock()
        self._subscriber = self._bus.subscribe("*", self._on_event, name="state_manager")

    def register_reducer(self, aggregate_type: str, reducer: Reducer) -> None:
        """Register a reducer for an aggregate type.

        ``aggregate_type`` is typically the prefix of event topics
        (e.g. ``task`` for ``task.created``, ``task.completed``).
        """
        self._reducers[aggregate_type] = reducer

    async def _on_event(self, event: Event) -> None:
        """Handle a bus event: find the reducer, apply it, update state."""
        # Derive the aggregate type from the topic (e.g. 'task.created' → 'task')
        aggregate_type = event.topic.split(".", 1)[0]
        reducer = self._reducers.get(aggregate_type)
        if reducer is None:
            return  # no reducer registered — ignore

        # Derive the aggregate ID from the event
        # Convention: payload['aggregate_id'] if present, else correlation_id
        aggregate_id = event.payload.get("aggregate_id", event.correlation_id)
        if not isinstance(aggregate_id, UUID):
            try:
                aggregate_id = UUID(str(aggregate_id))
            except (ValueError, TypeError):
                _log.warning(
                    "state.no_aggregate_id", event_topic=event.topic, event_id=str(event.id)
                )
                return

        async with self._lock:
            current = self._states.get(aggregate_id)
            try:
                new_state = reducer(current, event)
            except Exception:
                _log.exception(
                    "state.reducer_failed",
                    aggregate_type=aggregate_type,
                    aggregate_id=str(aggregate_id),
                    event_topic=event.topic,
                )
                return

            if new_state is not None:
                self._states[aggregate_id] = new_state
            elif aggregate_id in self._states:
                # Reducer returned None — aggregate is deleted
                del self._states[aggregate_id]

            self._event_counts[aggregate_id] += 1
            if self._event_counts[aggregate_id] % self._snapshot_interval == 0:
                await self._take_snapshot(aggregate_id, new_state)

    async def _take_snapshot(self, aggregate_id: AggregateId, state: Aggregate | None) -> None:
        """Take and store a snapshot (in-memory in v1; persistent store in v1.1)."""
        if state is None:
            return
        snapshot = Snapshot(
            aggregate_id=aggregate_id,
            sequence=self._event_counts[aggregate_id],
            state=state.model_dump(),
            taken_at=__import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        )
        self._snapshots[aggregate_id] = snapshot
        _log.debug(
            "state.snapshot_taken", aggregate_id=str(aggregate_id), sequence=snapshot.sequence
        )

    async def get(self, aggregate_id: AggregateId) -> Aggregate | None:
        """Return the current state of an aggregate, or None if not found."""
        async with self._lock:
            return self._states.get(aggregate_id)

    async def get_snapshot(self, aggregate_id: AggregateId) -> Snapshot | None:
        """Return the latest snapshot for an aggregate (for crash recovery)."""
        async with self._lock:
            return self._snapshots.get(aggregate_id)

    async def list_aggregates(self, prefix: str | None = None) -> list[AggregateId]:
        """Return all aggregate IDs (optionally filtered by type prefix)."""
        async with self._lock:
            if prefix is None:
                return list(self._states.keys())
            return [
                aid
                for aid, state in self._states.items()
                if state.__class__.__name__.lower().startswith(prefix.lower())
            ]

    async def shutdown(self) -> None:
        """Unsubscribe from the bus."""
        self._bus.unsubscribe(self._subscriber)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_INSTANCE: StateManager | None = None


def init_state_manager(bus: EventBus | None = None, **kwargs: Any) -> StateManager:
    """Initialize the global state manager."""
    global _INSTANCE
    _INSTANCE = StateManager(bus=bus, **kwargs)
    return _INSTANCE


def get_state_manager() -> StateManager:
    """Return the global state manager."""
    if _INSTANCE is None:
        raise RuntimeError("StateManager not initialized. Call init_state_manager() first.")
    return _INSTANCE


def set_state_manager(mgr: StateManager) -> None:
    """Set the global state manager (for testing)."""
    global _INSTANCE
    _INSTANCE = mgr
