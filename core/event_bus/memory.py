"""In-memory event store — for tests and ephemeral runs.

Not durable across process restarts. Use SQLiteEventStore for anything
that needs to survive a crash.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from core.contracts.event import Event


class InMemoryEventStore:
    """List-backed event store. Thread-safe via a single lock."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._by_stream: dict[str, list[Event]] = defaultdict(list)
        self._sequence: dict[str | None, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def append(self, event: Event) -> None:
        """Append an event. Assigns a sequence number per stream."""
        async with self._lock:
            stream = str(event.correlation_id)
            event = event.model_copy(update={"sequence": self._sequence[stream] + 1})
            self._sequence[stream] += 1
            self._sequence[None] += 1  # global counter
            self._events.append(event)
            self._by_stream[stream].append(event)

    async def replay(
        self,
        stream_id: str | None = None,
        from_sequence: int = 0,
        limit: int | None = None,
    ) -> list[Event]:
        """Replay events."""
        async with self._lock:
            if stream_id is None:
                events = [e for e in self._events if e.sequence > from_sequence]
            else:
                events = [
                    e for e in self._by_stream.get(stream_id, []) if e.sequence > from_sequence
                ]
            if limit is not None:
                events = events[:limit]
            return list(events)

    async def get_latest_sequence(self, stream_id: str | None = None) -> int:
        """Return the latest sequence number."""
        async with self._lock:
            return self._sequence[stream_id]

    async def close(self) -> None:
        """No-op for in-memory store."""
        return
