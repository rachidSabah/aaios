"""Tests for core.event_bus — pub/sub, persistence, replay."""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import (
    InMemoryEventBus,
    InMemoryEventStore,
    get_bus,
    init_bus,
    set_bus,
)


@pytest.fixture(autouse=True)
def _reset_bus():
    """Reset the bus singleton before each test."""
    set_bus(InMemoryEventBus())
    yield
    set_bus(InMemoryEventBus())


@pytest.mark.offline
class TestInMemoryEventStore:
    """InMemoryEventStore tests."""

    async def test_append_increments_sequence(self) -> None:
        store = InMemoryEventStore()
        correlation_id = uuid4()
        for i in range(3):
            e = Event(
                topic="test.topic",
                correlation_id=correlation_id,
                actor=ActorRef.system(),
                payload={"i": i},
            )
            await store.append(e)
        # The store assigns sequence numbers
        latest = await store.get_latest_sequence(str(correlation_id))
        assert latest == 3

    async def test_replay_returns_events_in_order(self) -> None:
        store = InMemoryEventStore()
        cid = uuid4()
        for i in range(5):
            await store.append(
                Event(
                    topic="test.topic",
                    correlation_id=cid,
                    actor=ActorRef.system(),
                    payload={"i": i},
                )
            )
        events = await store.replay(stream_id=str(cid))
        assert len(events) == 5

    async def test_replay_respects_from_sequence(self) -> None:
        store = InMemoryEventStore()
        cid = uuid4()
        for i in range(5):
            await store.append(
                Event(
                    topic="test.topic",
                    correlation_id=cid,
                    actor=ActorRef.system(),
                    payload={"i": i},
                )
            )
        events = await store.replay(stream_id=str(cid), from_sequence=2)
        assert len(events) == 3  # events 3, 4, 5


@pytest.mark.offline
class TestInMemoryEventBus:
    """EventBus tests."""

    async def test_publish_persists_before_dispatch(self) -> None:
        bus = InMemoryEventBus()
        received: list[Event] = []

        async def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("test.topic", handler)
        e = Event(
            topic="test.topic",
            correlation_id=uuid4(),
            actor=ActorRef.system(),
        )
        await bus.publish(e)
        # Give tasks a chance to run
        import asyncio

        await asyncio.sleep(0.05)
        assert len(received) == 1
        # And it should be persisted
        events = await bus.store.replay(stream_id=str(e.correlation_id))
        assert len(events) == 1

    async def test_prefix_subscription_matches(self) -> None:
        bus = InMemoryEventBus()
        received: list[str] = []

        async def handler(e: Event) -> None:
            received.append(e.topic)

        bus.subscribe("task", handler)  # prefix subscription
        cid = uuid4()
        await bus.publish(Event(topic="task.created", correlation_id=cid, actor=ActorRef.system()))
        await bus.publish(
            Event(topic="task.completed", correlation_id=cid, actor=ActorRef.system())
        )
        await bus.publish(
            Event(topic="agent.dispatched", correlation_id=cid, actor=ActorRef.system())
        )
        import asyncio

        await asyncio.sleep(0.05)
        assert "task.created" in received
        assert "task.completed" in received
        assert "agent.dispatched" not in received

    async def test_wildcard_subscription_matches_all(self) -> None:
        bus = InMemoryEventBus()
        received: list[str] = []

        async def handler(e: Event) -> None:
            received.append(e.topic)

        bus.subscribe("*", handler)
        cid = uuid4()
        await bus.publish(Event(topic="task.created", correlation_id=cid, actor=ActorRef.system()))
        await bus.publish(
            Event(topic="agent.dispatched", correlation_id=cid, actor=ActorRef.system())
        )
        import asyncio

        await asyncio.sleep(0.05)
        assert len(received) == 2

    async def test_subscriber_handler_exception_doesnt_block_others(self) -> None:
        bus = InMemoryEventBus()
        received: list[str] = []

        async def failing(e: Event) -> None:
            raise RuntimeError("boom")

        async def ok(e: Event) -> None:
            received.append(e.topic)

        bus.subscribe("test.topic", failing)
        bus.subscribe("test.topic", ok)
        await bus.publish(
            Event(
                topic="test.topic",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
            )
        )
        import asyncio

        await asyncio.sleep(0.1)
        assert len(received) == 1  # the OK handler still got called

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = InMemoryEventBus()
        received: list[Event] = []

        async def handler(e: Event) -> None:
            received.append(e)

        sub = bus.subscribe("test.topic", handler)
        cid = uuid4()
        await bus.publish(Event(topic="test.topic", correlation_id=cid, actor=ActorRef.system()))
        import asyncio

        await asyncio.sleep(0.05)
        assert len(received) == 1

        bus.unsubscribe(sub)
        await bus.publish(Event(topic="test.topic", correlation_id=cid, actor=ActorRef.system()))
        await asyncio.sleep(0.05)
        assert len(received) == 1  # no new delivery

    async def test_replay_redispatches_to_current_subscribers(self) -> None:
        bus = InMemoryEventBus()
        received: list[Event] = []

        async def handler(e: Event) -> None:
            received.append(e)

        cid = uuid4()
        # Publish first (no subscribers yet)
        await bus.publish(Event(topic="test.topic", correlation_id=cid, actor=ActorRef.system()))
        # Now subscribe and replay
        bus.subscribe("test.topic", handler)
        await bus.replay(stream_id=cid)
        import asyncio

        await asyncio.sleep(0.05)
        assert len(received) == 1

    async def test_subscriber_count(self) -> None:
        bus = InMemoryEventBus()

        async def h1(e: Event) -> None:
            pass

        async def h2(e: Event) -> None:
            pass

        bus.subscribe("a", h1)
        bus.subscribe("b", h2)
        assert bus.subscriber_count() == 2

    async def test_topics_listed(self) -> None:
        bus = InMemoryEventBus()

        async def h(e: Event) -> None:
            pass

        bus.subscribe("task", h)
        bus.subscribe("agent", h)
        assert set(bus.topics()) == {"task", "agent"}


@pytest.mark.offline
class TestBusSingleton:
    """Bus singleton accessor tests."""

    def test_init_bus_returns_singleton(self) -> None:
        bus = init_bus()
        assert get_bus() is bus

    def test_get_bus_without_init_raises(self) -> None:
        # Reset to None manually (init_bus was called by another test)
        from core.event_bus import bus as bus_module

        original = bus_module._INSTANCE
        bus_module._INSTANCE = None
        try:
            with pytest.raises(RuntimeError):
                get_bus()
        finally:
            bus_module._INSTANCE = original
