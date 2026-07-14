"""Built-in reducers for the core aggregates.

A reducer is a pure function: ``(state, event) -> state``. It must not
perform I/O, must not raise (except for genuinely invalid events).

Each reducer matches an aggregate type (the prefix of event topics). When
an event arrives, the state manager looks up the reducer by the topic
prefix and applies it.

To add a new aggregate:
  1. Subclass ``Aggregate`` to define its state shape.
  2. Write a reducer function: ``def my_reducer(state, event) -> MyAggregate | None``.
  3. Register it: ``state_manager.register_reducer('my_aggregate', my_reducer)``.
"""

from __future__ import annotations

from core.contracts.event import Event, EventTopic
from core.contracts.task import TaskStatus
from core.state.manager import Aggregate, Reducer

# ---------------------------------------------------------------------------
# Task aggregate
# ---------------------------------------------------------------------------


class TaskAggregate(Aggregate):
    """The state of a Task."""

    status: TaskStatus = TaskStatus.PENDING
    goal: str = ""
    priority: str = "normal"
    submitted_by: str = ""
    completed_at: str | None = None
    failed_reason: str | None = None
    cancelled_reason: str | None = None


def task_reducer(state: TaskAggregate | None, event: Event) -> TaskAggregate | None:
    """Reducer for the Task aggregate.

    Matches events with topic prefix ``task.`` (task.created, task.completed, etc.).
    """
    if state is None:
        # First event must be task.created
        if event.topic != EventTopic.TASK_CREATED:
            return None
        return TaskAggregate(
            id=event.correlation_id,
            version=1,
            status=TaskStatus.PENDING,
            goal=str(event.payload.get("goal", "")),
            priority=str(event.payload.get("priority", "normal")),
            submitted_by=str(event.payload.get("submitted_by", "")),
        )

    new = state.model_copy(update={"version": state.version + 1})

    if event.topic == EventTopic.TASK_QUEUED:
        new.status = TaskStatus.QUEUED
    elif event.topic == EventTopic.TASK_STARTED:
        new.status = TaskStatus.RUNNING
    elif event.topic == EventTopic.TASK_PAUSED:
        new.status = TaskStatus.PAUSED
    elif event.topic == EventTopic.TASK_RESUMED:
        new.status = TaskStatus.RUNNING
    elif event.topic == EventTopic.TASK_COMPLETED:
        new.status = TaskStatus.COMPLETED
        new.completed_at = event.timestamp.isoformat()
    elif event.topic == EventTopic.TASK_FAILED:
        new.status = TaskStatus.FAILED
        new.failed_reason = str(event.payload.get("reason", ""))
        new.completed_at = event.timestamp.isoformat()
    elif event.topic == EventTopic.TASK_CANCELLED:
        new.status = TaskStatus.CANCELLED
        new.cancelled_reason = str(event.payload.get("reason", ""))
        new.completed_at = event.timestamp.isoformat()
    # Other events (step.*, agent.*) are not relevant to the Task aggregate.

    return new


# ---------------------------------------------------------------------------
# Default reducer registry
# ---------------------------------------------------------------------------


def default_reducer(state: Aggregate | None, event: Event) -> Aggregate | None:
    """Fallback reducer for aggregates without a specific reducer.

    Returns the state unchanged. Useful for events that don't affect state.
    """
    return state


# Registry of built-in reducers (for ``init_state_manager`` to use)
# Cast: the per-aggregate reducers are more specific than the generic Reducer
# signature, but they're structurally compatible (covariant return).
DEFAULT_REDUCERS: dict[str, Reducer] = {
    "task": task_reducer,  # type: ignore[dict-item]
}


__all__ = [
    "DEFAULT_REDUCERS",
    "TaskAggregate",
    "default_reducer",
    "task_reducer",
]
