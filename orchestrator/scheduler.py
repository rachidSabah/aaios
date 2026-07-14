"""Scheduler — recurring and delayed task submission.

Persists scheduled tasks to Windows Task Scheduler (on Windows) or an
in-process APScheduler-style loop (on Linux, v1.1). For Phase 5, we
implement the in-process loop on all platforms; the Windows Task Scheduler
delegation lands in Phase 14 (Windows deployment).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from core.contracts.timestamp import utc_now
from core.logging import get_logger
from orchestrator.contracts.schedule import ScheduleSpec, ScheduleType

_log = get_logger(__name__)

__all__ = ["ScheduledTask", "Scheduler"]


@dataclass
class ScheduledTask:
    """A scheduled task (internal tracking)."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    schedule: ScheduleSpec | None = None
    # The callable to invoke when the schedule fires
    callback: Any = None  # callable[[UUID], Awaitable[None]]
    # Tracking
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    enabled: bool = True
    # The task ID produced by the last invocation
    last_task_id: UUID | None = None


class Scheduler:
    """In-process scheduler.

    Runs a background loop that checks every second for due scheduled tasks
    and invokes their callbacks. The callbacks are responsible for submitting
    plans to the Orchestrator.
    """

    def __init__(self, *, check_interval_s: float = 1.0) -> None:
        self._tasks: dict[UUID, ScheduledTask] = {}
        self._check_interval_s = check_interval_s
        self._loop_task: asyncio.Task[None] | None = None
        self._running: bool = False

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(
            self._loop(),
            name="scheduler.loop",
        )
        _log.info("scheduler.started")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        _log.info("scheduler.stopped")

    async def schedule(
        self,
        schedule: ScheduleSpec,
        callback: Any,  # callable[[UUID], Awaitable[None]]
        *,
        name: str = "",
    ) -> UUID:
        """Schedule a task. Returns the scheduled task ID.

        Args:
            schedule: when to run.
            callback: async callable invoked with the scheduled task ID.
            name: human-readable name.
        """
        errors = schedule.validate_spec()
        if errors:
            raise ValueError(f"Invalid schedule: {errors}")

        task = ScheduledTask(
            id=uuid4(),
            name=name,
            schedule=schedule,
            callback=callback,
            next_run_at=self._compute_next_run(schedule, utc_now()),
        )
        self._tasks[task.id] = task
        _log.info(
            "scheduler.scheduled",
            task_id=str(task.id),
            name=name,
            schedule_type=schedule.schedule_type.value,
            next_run_at=task.next_run_at.isoformat() if task.next_run_at else None,
        )
        return task.id

    def unschedule(self, task_id: UUID) -> bool:
        """Unschedule a task. Returns True if found."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            _log.info("scheduler.unscheduled", task_id=str(task_id))
            return True
        return False

    def list_scheduled(self) -> list[ScheduledTask]:
        """Return all scheduled tasks (for the dashboard)."""
        return list(self._tasks.values())

    def get(self, task_id: UUID) -> ScheduledTask | None:
        """Return a scheduled task, or None."""
        return self._tasks.get(task_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Background loop: fire due tasks."""
        while self._running:
            try:
                now = utc_now()
                due = [
                    t
                    for t in self._tasks.values()
                    if t.enabled and t.next_run_at is not None and t.next_run_at <= now
                ]
                for task in due:
                    asyncio.create_task(self._fire(task))
            except asyncio.CancelledError:
                break
            except Exception:
                _log.exception("scheduler.loop_error")
            await asyncio.sleep(self._check_interval_s)

    async def _fire(self, task: ScheduledTask) -> None:
        """Fire a scheduled task: invoke its callback and schedule the next run."""
        task.last_run_at = utc_now()
        task.run_count += 1
        try:
            await task.callback(task.id)
            _log.info(
                "scheduler.fired",
                task_id=str(task.id),
                name=task.name,
                run_count=task.run_count,
            )
        except Exception:
            _log.exception("scheduler.callback_failed", task_id=str(task.id))

        # Check if we should schedule the next run
        assert task.schedule is not None
        if task.schedule.max_runs is not None and task.run_count >= task.schedule.max_runs:
            task.enabled = False
            task.next_run_at = None
            _log.info("scheduler.max_runs_reached", task_id=str(task.id))
            return
        if task.schedule.until is not None and utc_now() >= task.schedule.until:
            task.enabled = False
            task.next_run_at = None
            _log.info("scheduler.until_reached", task_id=str(task.id))
            return
        task.next_run_at = self._compute_next_run(task.schedule, utc_now())

    @staticmethod
    def _compute_next_run(schedule: ScheduleSpec, now: datetime) -> datetime | None:
        """Compute the next run time for a schedule."""
        if schedule.schedule_type == ScheduleType.ONE_TIME:
            # ONE_TIME runs once at run_at, then stops
            if schedule.run_at is not None and schedule.run_at > now:
                return schedule.run_at
            return None  # already past
        if schedule.schedule_type == ScheduleType.INTERVAL:
            assert schedule.interval_s is not None
            return now + timedelta(seconds=schedule.interval_s)
        if schedule.schedule_type == ScheduleType.CRON:
            # Phase 5: simplified — just run every minute (real cron parsing in Phase 14)
            # The Windows Task Scheduler integration will handle real cron.
            return now + timedelta(minutes=1)
        # The above is exhaustive over ScheduleType (ONE_TIME, INTERVAL, CRON).
        # mypy knows this, so no fallback is needed.
