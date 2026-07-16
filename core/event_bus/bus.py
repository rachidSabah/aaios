"""The Event Bus — async pub/sub with persistence and replay.

Design:
  - ``publish(event)`` awaits the store's ``append()`` (INV-04), then
    schedules each subscriber's handler as a task.
  - Subscribers register with ``subscribe(topic, handler)``. Topic matching
    is exact OR prefix-with-dot — subscribing to ``agent`` matches
    ``agent.dispatched`` and ``agent.health_changed`` but NOT ``agents.foo``.
  - Handlers are async. If a handler raises, the error is logged but does
    not affect other subscribers (at-least-once; idempotency required).
  - ``replay(stream_id)`` re-publishes events from the store to current
    subscribers — used for crash recovery and dashboard "replay task".

Two implementations:
  - InMemoryEventBus (default, single-process)
  - RedisEventBus (stubbed in v1; multi-process via Redis Streams)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from uuid import UUID

from core.contracts.event import Event
from core.event_bus.memory import InMemoryEventStore
from core.event_bus.store import EventStore
from core.logging import get_logger

_log = get_logger(__name__)

# Type alias for the handler signature
EventHandler = Callable[[Event], Awaitable[None]]


class Subscriber:
    """A registered subscriber."""

    def __init__(
        self,
        topic: str,
        handler: EventHandler,
        *,
        name: str | None = None,
    ) -> None:
        self.topic = topic
        self.handler = handler
        self.name = name or handler.__name__
        self.active = True

    def matches(self, event_topic: str) -> bool:
        """Return True if this subscriber's topic matches ``event_topic``.

        Match rules:
          - exact match: ``agent.dispatched`` matches ``agent.dispatched``
          - prefix match: ``agent`` matches ``agent.dispatched`` and
            ``agent.health_changed`` (but not ``agents.foo``)
          - wildcard ``*`` matches everything
          - trailing wildcard ``prefix.*`` matches any ``prefix.<segment>``
            (e.g. ``test.*`` matches ``test.integration``)
        """
        if self.topic == "*":
            return True
        if self.topic == event_topic:
            return True
        # Trailing wildcard: "test.*" matches "test.anything"
        if self.topic.endswith(".*"):
            prefix = self.topic[:-2]
            return event_topic.startswith(prefix + ".")
        return event_topic.startswith(self.topic + ".")


class EventBus:
    """Abstract event bus. See ``InMemoryEventBus`` for the default impl."""

    async def publish(self, event: Event) -> None:
        """Publish an event. Persists first (INV-04), then dispatches."""
        raise NotImplementedError

    def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        *,
        name: str | None = None,
    ) -> Subscriber:
        """Subscribe to events matching ``topic``. Returns the Subscriber handle."""
        raise NotImplementedError

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Unsubscribe."""
        raise NotImplementedError

    async def replay(
        self,
        stream_id: UUID | str | None = None,
        from_sequence: int = 0,
    ) -> None:
        """Replay events from the store to current subscribers."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release resources."""
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    """In-process event bus. Default for single-process deployments."""

    def __init__(self, store: EventStore | None = None) -> None:
        self._store: EventStore = store or InMemoryEventStore()
        self._subscribers: list[Subscriber] = []
        self._by_topic: dict[str, list[Subscriber]] = defaultdict(list)
        self._lock = asyncio.Lock()

    @property
    def store(self) -> EventStore:
        """The underlying event store."""
        return self._store

    async def publish(self, event: Event) -> None:
        """Publish: persist first (INV-04), then dispatch to subscribers."""
        # 1. Persist (await — INV-04)
        await self._store.append(event)

        # 2. Dispatch to matching subscribers
        # Take a snapshot under the lock to avoid mutation-during-iteration
        async with self._lock:
            matching = [s for s in self._subscribers if s.active and s.matches(event.topic)]

        # 3. Schedule each handler — errors are caught, don't block others
        for sub in matching:
            asyncio.create_task(self._dispatch(sub, event))

    async def _dispatch(self, sub: Subscriber, event: Event) -> None:
        """Dispatch a single event to a single subscriber. Catches all errors."""
        try:
            await sub.handler(event)
        except Exception:
            _log.exception(
                "eventbus.subscriber_failed",
                subscriber=sub.name,
                topic=sub.topic,
                event_id=str(event.id),
                event_topic=event.topic,
            )

    def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        *,
        name: str | None = None,
    ) -> Subscriber:
        """Subscribe to events matching ``topic``."""
        sub = Subscriber(topic, handler, name=name)
        self._subscribers.append(sub)
        self._by_topic[topic].append(sub)
        return sub

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove a subscriber."""
        subscriber.active = False
        try:
            self._subscribers.remove(subscriber)
        except ValueError:
            pass
        if subscriber.topic in self._by_topic:
            try:
                self._by_topic[subscriber.topic].remove(subscriber)
            except ValueError:
                pass

    async def replay(
        self,
        stream_id: UUID | str | None = None,
        from_sequence: int = 0,
    ) -> None:
        """Replay events from the store to current subscribers."""
        stream = str(stream_id) if stream_id is not None else None
        events = await self._store.replay(stream_id=stream, from_sequence=from_sequence)
        _log.info("eventbus.replay_start", count=len(events), stream_id=stream)
        for event in events:
            async with self._lock:
                matching = [s for s in self._subscribers if s.active and s.matches(event.topic)]
            for sub in matching:
                asyncio.create_task(self._dispatch(sub, event))

    async def close(self) -> None:
        """Release resources."""
        await self._store.close()

    # --- introspection (for tests + dashboard) ---

    def subscriber_count(self) -> int:
        """Return the number of active subscribers."""
        return sum(1 for s in self._subscribers if s.active)

    def topics(self) -> list[str]:
        """Return the unique set of subscribed topics."""
        return sorted({s.topic for s in self._subscribers if s.active})


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_INSTANCE: EventBus | None = None


def init_bus(store: EventStore | None = None) -> EventBus:
    """Initialize the global event bus."""
    global _INSTANCE
    _INSTANCE = InMemoryEventBus(store=store)
    return _INSTANCE


def get_bus() -> EventBus:
    """Return the global event bus.

    Raises if ``init_bus()`` hasn't been called.
    """
    if _INSTANCE is None:
        raise RuntimeError("EventBus not initialized. Call init_bus() first.")
    return _INSTANCE


def set_bus(bus: EventBus) -> None:
    """Set the global event bus (for testing)."""
    global _INSTANCE
    _INSTANCE = bus
