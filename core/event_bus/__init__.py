"""Event Bus — typed async pub/sub with persistence.

The Event Bus is the spine of the system. Every state change flows through
it as a typed Event. Subscribers register against topics with async handlers.
The bus guarantees at-least-once delivery within a process; idempotency is
the subscriber's responsibility.

INV-04: every event is persisted to the event store BEFORE any subscriber is
allowed to observe a side effect. The persistence is synchronous (await
the store's ack) before any subscriber is dispatched.

Two adapters:
  - InProcessBus: default; asyncio.Queue per subscriber. Single-process.
  - RedisBus: optional; Redis Streams for multi-process. Stubbed in v1.

The event store is pluggable:
  - SQLiteEventStore: default; one file. Used for dev, test, single-user prod.
  - PostgresEventStore: optional; for production. Stubbed in v1.
"""

from __future__ import annotations

from core.event_bus.bus import EventBus, Subscriber, get_bus, init_bus, set_bus
from core.event_bus.memory import InMemoryEventStore
from core.event_bus.store import EventStore

__all__ = [
    "EventBus",
    "EventStore",
    "InMemoryEventBus",
    "InMemoryEventStore",
    "Subscriber",
    "get_bus",
    "init_bus",
    "set_bus",
]


# Convenience alias — the in-process implementation is the default
from core.event_bus.bus import InMemoryEventBus
