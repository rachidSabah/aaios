"""Priority task queue — 5 levels with aging to prevent starvation.

Levels (highest priority first):
    critical > high > normal > low > background

Within a level, FIFO. Across levels, strict priority — but a task that has
waited longer than ``aging_threshold_s`` gets promoted one level. This
prevents starvation of low-priority tasks under sustained high-priority load.

Concurrency is limited per level (configurable). The queue does NOT enforce
concurrency itself — the Orchestrator asks ``can_dispatch(level)`` and
``dispatched(level)`` to track in-flight tasks.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from core.contracts.timestamp import utc_now
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["Priority", "PriorityQueue", "QueueItem"]


class Priority(StrEnum):
    """The 5 priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"

    @classmethod
    def from_string(cls, value: str) -> Priority:
        """Parse a priority string (case-insensitive). Raises ValueError if invalid."""
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"Invalid priority: {value!r}") from e

    @property
    def level(self) -> int:
        """Numeric level (0 = highest priority). For internal sorting."""
        return _PRIORITY_LEVELS[self]


_PRIORITY_LEVELS: dict[Priority, int] = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
    Priority.BACKGROUND: 4,
}

# Default concurrency limits per priority level
DEFAULT_CONCURRENCY: dict[Priority, int] = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 4,
    Priority.NORMAL: 8,
    Priority.LOW: 4,
    Priority.BACKGROUND: 2,
}


@dataclass
class QueueItem:
    """An item in the priority queue."""

    plan_id: UUID
    task_id: UUID
    priority: Priority
    enqueued_at: datetime = field(default_factory=utc_now)
    # The effective priority (may be higher than `priority` due to aging)
    effective_priority: Priority | None = None

    def age_s(self, now: datetime | None = None) -> float:
        """Return how long this item has been in the queue, in seconds."""
        now = now or utc_now()
        return (now - self.enqueued_at).total_seconds()

    def get_effective_priority(self, aging_threshold_s: float) -> Priority:
        """Return the effective priority, promoting if aged beyond the threshold.

        Each ``aging_threshold_s`` seconds spent waiting promotes the item
        one level (up to CRITICAL).
        """
        if self.effective_priority is not None:
            return self.effective_priority
        age = self.age_s()
        if age < aging_threshold_s:
            return self.priority
        # Promote one level per threshold period
        promotions = int(age / aging_threshold_s)
        current_level = self.priority.level
        new_level = max(0, current_level - promotions)
        for p in Priority:
            if p.level == new_level:
                return p
        return self.priority


class PriorityQueue:
    """A priority queue with aging.

    Not thread-safe in the strictest sense, but all access is via the
    asyncio event loop (single-threaded by convention).
    """

    def __init__(
        self,
        *,
        concurrency: dict[Priority, int] | None = None,
        aging_threshold_s: float = 60.0,
    ) -> None:
        self._queues: dict[Priority, deque[QueueItem]] = {p: deque() for p in Priority}
        self._concurrency = concurrency or dict(DEFAULT_CONCURRENCY)
        self._aging_threshold_s = aging_threshold_s
        self._in_flight: dict[Priority, set[UUID]] = {p: set() for p in Priority}
        self._not_empty = asyncio.Event()
        self._lock = asyncio.Lock()

    async def enqueue(self, item: QueueItem) -> None:
        """Add an item to the queue."""
        async with self._lock:
            self._queues[item.priority].append(item)
            self._not_empty.set()
            _log.info(
                "queue.enqueued",
                plan_id=str(item.plan_id),
                priority=item.priority.value,
                queue_depth=self.depth(),
            )

    async def dequeue(self) -> QueueItem:
        """Remove and return the highest-priority item.

        Blocks if the queue is empty. Respects per-level concurrency limits:
        if the highest-priority item's level is at capacity, falls through
        to the next level.
        """
        while True:
            async with self._lock:
                item = self._try_dequeue()
                if item is not None:
                    self._in_flight[item.get_effective_priority(self._aging_threshold_s)].add(
                        item.plan_id
                    )
                    _log.info(
                        "queue.dispatched",
                        plan_id=str(item.plan_id),
                        priority=item.priority.value,
                        effective=item.get_effective_priority(self._aging_threshold_s).value,
                        wait_s=item.age_s(),
                    )
                    return item
            # Wait for items to become available
            self._not_empty.clear()
            await self._not_empty.wait()

    def _try_dequeue(self) -> QueueItem | None:
        """Try to dequeue without blocking. Returns None if nothing available
        or all available levels are at capacity.
        """
        # Build a list of (effective_level, queue, item) for the head of each queue
        candidates: list[tuple[int, Priority, QueueItem]] = []
        for priority in Priority:
            queue = self._queues[priority]
            if not queue:
                continue
            head = queue[0]
            effective = head.get_effective_priority(self._aging_threshold_s)
            # Check concurrency limit at the effective level
            if len(self._in_flight[effective]) >= self._concurrency[effective]:
                continue
            candidates.append((effective.level, priority, head))
        if not candidates:
            return None
        # Pick the candidate with the lowest (highest priority) effective level
        candidates.sort(key=lambda c: c[0])
        _, source_priority, item = candidates[0]
        self._queues[source_priority].popleft()
        return item

    async def complete(self, plan_id: UUID, priority: Priority) -> None:
        """Mark a dispatched item as complete (frees a concurrency slot)."""
        async with self._lock:
            # The item may have been promoted; check all levels
            for p in Priority:
                if plan_id in self._in_flight[p]:
                    self._in_flight[p].discard(plan_id)
                    _log.info(
                        "queue.completed",
                        plan_id=str(plan_id),
                        priority=p.value,
                    )
                    return
            # Not found — might have been cancelled
            _log.warning("queue.complete_not_found", plan_id=str(plan_id))

    def depth(self, priority: Priority | None = None) -> int:
        """Return the queue depth (total, or for a specific priority)."""
        if priority is not None:
            return len(self._queues[priority])
        return sum(len(q) for q in self._queues.values())

    def in_flight(self, priority: Priority | None = None) -> int:
        """Return the in-flight count (total, or for a specific priority)."""
        if priority is not None:
            return len(self._in_flight[priority])
        return sum(len(s) for s in self._in_flight.values())

    def is_empty(self) -> bool:
        """Return True if the queue is empty (no pending items)."""
        return self.depth() == 0

    async def remove(self, plan_id: UUID) -> bool:
        """Remove an item from the queue (e.g. on cancellation).

        Returns True if the item was found and removed.
        """
        async with self._lock:
            for priority in Priority:
                queue = self._queues[priority]
                for i, item in enumerate(queue):
                    if item.plan_id == plan_id:
                        del queue[i]
                        _log.info("queue.removed", plan_id=str(plan_id), priority=priority.value)
                        return True
            # Also check in-flight
            for p in Priority:
                if plan_id in self._in_flight[p]:
                    self._in_flight[p].discard(plan_id)
                    _log.info("queue.removed_inflight", plan_id=str(plan_id), priority=p.value)
                    return True
            return False

    def snapshot(self) -> list[QueueItem]:
        """Return a snapshot of all queued items (for the dashboard)."""
        result: list[QueueItem] = []
        for queue in self._queues.values():
            result.extend(queue)
        return result
