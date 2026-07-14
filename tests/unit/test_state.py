"""Tests for core.state — event-sourced state manager with reducers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.contracts.actor import ActorRef
from core.contracts.event import Event, EventTopic
from core.contracts.task import TaskStatus
from core.event_bus import InMemoryEventBus
from core.state import StateManager, init_state_manager
from core.state.reducers import DEFAULT_REDUCERS, TaskAggregate


@pytest.fixture
async def bus() -> InMemoryEventBus:
    """Fresh event bus per test."""
    return InMemoryEventBus()


@pytest.fixture
async def state_manager(bus: InMemoryEventBus) -> StateManager:
    """Fresh state manager with default reducers. Cleans up after test."""
    sm = StateManager(bus=bus)
    for agg_type, reducer in DEFAULT_REDUCERS.items():
        sm.register_reducer(agg_type, reducer)
    yield sm
    await sm.shutdown()


@pytest.mark.offline
class TestTaskReducer:
    """TaskAggregate reducer tests."""

    async def test_task_created_initializes_state(
        self,
        bus: InMemoryEventBus,
        state_manager: StateManager,
    ) -> None:
        task_id = uuid4()
        await bus.publish(
            Event(
                topic=EventTopic.TASK_CREATED,
                correlation_id=task_id,
                actor=ActorRef.user("alice"),
                payload={"goal": "write tests", "priority": "high", "submitted_by": "alice"},
            )
        )
        # Wait for the subscriber to process
        import asyncio

        await asyncio.sleep(0.05)

        state = await state_manager.get(task_id)
        assert state is not None
        assert isinstance(state, TaskAggregate)
        assert state.status == TaskStatus.PENDING
        assert state.goal == "write tests"
        assert state.priority == "high"
        assert state.version == 1

    async def test_task_lifecycle_transitions(
        self,
        bus: InMemoryEventBus,
        state_manager: StateManager,
    ) -> None:
        task_id = uuid4()
        # Create → Queue → Start → Pause → Resume → Complete
        events = [
            Event(
                topic=EventTopic.TASK_CREATED,
                correlation_id=task_id,
                actor=ActorRef.system(),
                payload={"goal": "x"},
            ),
            Event(topic=EventTopic.TASK_QUEUED, correlation_id=task_id, actor=ActorRef.system()),
            Event(topic=EventTopic.TASK_STARTED, correlation_id=task_id, actor=ActorRef.system()),
            Event(topic=EventTopic.TASK_PAUSED, correlation_id=task_id, actor=ActorRef.system()),
            Event(topic=EventTopic.TASK_RESUMED, correlation_id=task_id, actor=ActorRef.system()),
            Event(topic=EventTopic.TASK_COMPLETED, correlation_id=task_id, actor=ActorRef.system()),
        ]
        for e in events:
            await bus.publish(e)

        import asyncio

        await asyncio.sleep(0.1)

        state = await state_manager.get(task_id)
        assert state is not None
        assert state.status == TaskStatus.COMPLETED
        assert state.version == 6  # 1 (created) + 5 transitions
        assert state.completed_at is not None

    async def test_task_failed_records_reason(
        self,
        bus: InMemoryEventBus,
        state_manager: StateManager,
    ) -> None:
        task_id = uuid4()
        await bus.publish(
            Event(
                topic=EventTopic.TASK_CREATED,
                correlation_id=task_id,
                actor=ActorRef.system(),
                payload={"goal": "x"},
            )
        )
        await bus.publish(
            Event(
                topic=EventTopic.TASK_FAILED,
                correlation_id=task_id,
                actor=ActorRef.system(),
                payload={"reason": "agent crashed"},
            )
        )
        import asyncio

        await asyncio.sleep(0.05)

        state = await state_manager.get(task_id)
        assert state is not None
        assert state.status == TaskStatus.FAILED
        assert state.failed_reason == "agent crashed"

    async def test_first_event_must_be_created(
        self,
        bus: InMemoryEventBus,
        state_manager: StateManager,
    ) -> None:
        task_id = uuid4()
        # Send TASK_STARTED without TASK_CREATED first
        await bus.publish(
            Event(
                topic=EventTopic.TASK_STARTED,
                correlation_id=task_id,
                actor=ActorRef.system(),
            )
        )
        import asyncio

        await asyncio.sleep(0.05)
        state = await state_manager.get(task_id)
        assert state is None  # reducer returned None

    async def test_no_reducer_for_unknown_topic(
        self,
        bus: InMemoryEventBus,
        state_manager: StateManager,
    ) -> None:
        # Topic prefix has no registered reducer
        await bus.publish(
            Event(
                topic="unknown_topic.something",
                correlation_id=uuid4(),
                actor=ActorRef.system(),
            )
        )
        import asyncio

        await asyncio.sleep(0.05)
        # Should not crash; just no-op

    async def test_snapshot_taken_after_interval(
        self,
        bus: InMemoryEventBus,
    ) -> None:
        # Use a small snapshot interval for testing
        sm = StateManager(bus=bus, snapshot_interval=3)
        for agg_type, reducer in DEFAULT_REDUCERS.items():
            sm.register_reducer(agg_type, reducer)

        task_id = uuid4()
        await bus.publish(
            Event(
                topic=EventTopic.TASK_CREATED,
                correlation_id=task_id,
                actor=ActorRef.system(),
                payload={"goal": "x"},
            )
        )
        await bus.publish(
            Event(topic=EventTopic.TASK_QUEUED, correlation_id=task_id, actor=ActorRef.system())
        )
        await bus.publish(
            Event(topic=EventTopic.TASK_STARTED, correlation_id=task_id, actor=ActorRef.system())
        )

        import asyncio

        # Poll for the snapshot (the state manager's _on_event runs as a
        # fire-and-forget task, so we need to wait for it)
        snapshot = None
        for _ in range(20):  # up to ~2 seconds
            await asyncio.sleep(0.1)
            snapshot = await sm.get_snapshot(task_id)
            if snapshot is not None:
                break
        assert snapshot is not None, "Snapshot never taken"
        assert snapshot.sequence == 3

    async def test_list_aggregates(
        self,
        bus: InMemoryEventBus,
        state_manager: StateManager,
    ) -> None:
        task_id_1 = uuid4()
        task_id_2 = uuid4()
        await bus.publish(
            Event(
                topic=EventTopic.TASK_CREATED,
                correlation_id=task_id_1,
                actor=ActorRef.system(),
                payload={"goal": "x"},
            )
        )
        await bus.publish(
            Event(
                topic=EventTopic.TASK_CREATED,
                correlation_id=task_id_2,
                actor=ActorRef.system(),
                payload={"goal": "y"},
            )
        )
        import asyncio

        await asyncio.sleep(0.05)

        all_ids = await state_manager.list_aggregates()
        assert len(all_ids) == 2
        assert task_id_1 in all_ids
        assert task_id_2 in all_ids


@pytest.mark.offline
class TestStateManagerSingleton:
    """init_state_manager / get_state_manager tests."""

    async def test_init_returns_singleton(self, bus: InMemoryEventBus) -> None:
        sm = init_state_manager(bus=bus)
        try:
            from core.state import get_state_manager

            assert get_state_manager() is sm
        finally:
            await sm.shutdown()
            from core.state import set_state_manager

            set_state_manager(None)  # type: ignore[arg-type]
