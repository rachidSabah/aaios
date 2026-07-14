"""Event store — the persistent log of every event.

INV-04: the bus awaits ``append()`` before dispatching to subscribers.

Two implementations:
  - InMemoryEventStore: list-backed; for tests and ephemeral runs.
  - SQLiteEventStore: file-backed; the default for production single-user.
  - PostgresEventStore: stubbed; lands in Phase 8 with the security layer.
"""

from __future__ import annotations

from typing import Protocol

from core.contracts.event import Event


class EventStore(Protocol):
    """The persistent event store — append-only, replayable."""

    async def append(self, event: Event) -> None:
        """Persist an event. Must be durable before returning (INV-04)."""
        ...

    async def replay(
        self,
        stream_id: str | None = None,
        from_sequence: int = 0,
        limit: int | None = None,
    ) -> list[Event]:
        """Replay events from the store.

        Args:
            stream_id: if given, only events whose ``correlation_id`` matches.
            from_sequence: skip events with sequence < this (per stream).
            limit: max events to return.
        """
        ...

    async def get_latest_sequence(self, stream_id: str | None = None) -> int:
        """Return the latest sequence number for ``stream_id`` (or globally)."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...


class EventStoreError(RuntimeError):
    """Raised when the event store fails."""


__all__ = ["EventStore", "EventStoreError"]
