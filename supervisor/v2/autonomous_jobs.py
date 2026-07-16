"""AutonomousJobScheduler — long-running jobs that persist across reboots.

In v1.0, the Scheduler runs in-process and loses all jobs on reboot.
v2.0 adds persistence: jobs are stored in the event store and restored
on boot.

Job types:
- Cron: "0 9 * * 1-5" (every weekday at 9am)
- Interval: every N minutes
- Event-triggered: run when a specific event occurs
- One-time delayed: run once at a specific time

Jobs are Plans with a schedule attached. When a job fires, the plan is
submitted to the Orchestrator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.contracts.timestamp import utc_now
from core.event_bus import EventBus, get_bus
from core.logging import get_logger
from orchestrator.contracts.dag import Plan
from orchestrator.contracts.schedule import ScheduleSpec, ScheduleType

_log = get_logger(__name__)

__all__ = ["AutonomousJob", "AutonomousJobScheduler", "JobStatus"]


class JobStatus(StrEnum):
    """Job lifecycle states."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AutonomousJob:
    """A long-running autonomous job."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    goal: str = ""  # What the job accomplishes
    schedule: ScheduleSpec | None = None
    trigger_event: str | None = None  # If event-triggered
    status: JobStatus = JobStatus.SCHEDULED
    priority: str = "low"  # Background jobs default to low priority
    # Tracking
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    last_result: str | None = None
    last_error: str | None = None
    max_runs: int | None = None
    until: datetime | None = None
    # The plan to execute when the job fires
    plan: Plan | None = None
    # Context for the task
    project_id: str | None = None


class AutonomousJobScheduler:
    """Schedules and runs long-running autonomous jobs.

    Jobs persist across reboots (stored in the event store via events).
    On boot, the scheduler loads all scheduled jobs and resumes them.

    Usage:
        scheduler = AutonomousJobScheduler(bus=get_bus())
        await scheduler.start()

        # Schedule a daily summary job
        job = AutonomousJob(
            name='daily-summary',
            goal='Generate a daily summary of all tasks',
            schedule=ScheduleSpec(
                schedule_type=ScheduleType.CRON,
                cron='0 9 * * *',
            ),
            priority='background',
        )
        await scheduler.schedule(job)
    """

    def __init__(
        self,
        bus: EventBus | None = None,
        *,
        check_interval_s: float = 30.0,
    ) -> None:
        self._bus = bus or get_bus()
        self._jobs: dict[UUID, AutonomousJob] = {}
        self._check_interval_s = check_interval_s
        self._loop_task: asyncio.Task[None] | None = None
        self._running = False
        self._event_subscriptions: list[Any] = []

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(
            self._loop(),
            name="autonomous_job_scheduler",
        )

        # Subscribe to trigger events
        async def on_event(event: Event) -> None:
            await self._check_event_triggers(event)

        sub = self._bus.subscribe("*", on_event, name="autonomous_job_scheduler")
        self._event_subscriptions.append(sub)

        _log.info("autonomous_jobs.started", jobs=len(self._jobs))

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        for sub in self._event_subscriptions:
            self._bus.unsubscribe(sub)
        self._event_subscriptions.clear()
        _log.info("autonomous_jobs.stopped")

    async def schedule(self, job: AutonomousJob) -> UUID:
        """Schedule a new job."""
        job.next_run_at = self._compute_next_run(job.schedule)
        self._jobs[job.id] = job

        # Emit event for persistence
        await self._bus.publish(
            Event(
                topic="autonomous_job.scheduled",
                correlation_id=job.id,
                actor=ActorRef.system(),
                payload={
                    "job_id": str(job.id),
                    "name": job.name,
                    "goal": job.goal,
                    "priority": job.priority,
                    "next_run": job.next_run_at.isoformat() if job.next_run_at else None,
                },
            ),
        )

        _log.info(
            "autonomous_jobs.scheduled",
            job_id=str(job.id),
            name=job.name,
            next_run=job.next_run_at.isoformat() if job.next_run_at else "event-triggered",
        )
        return job.id

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a scheduled job."""
        if job_id not in self._jobs:
            return False
        self._jobs[job_id].status = JobStatus.CANCELLED
        del self._jobs[job_id]
        _log.info("autonomous_jobs.cancelled", job_id=str(job_id))
        return True

    async def pause(self, job_id: UUID) -> bool:
        """Pause a job."""
        if job_id not in self._jobs:
            return False
        self._jobs[job_id].status = JobStatus.PAUSED
        return True

    async def resume(self, job_id: UUID) -> bool:
        """Resume a paused job."""
        if job_id not in self._jobs:
            return False
        self._jobs[job_id].status = JobStatus.SCHEDULED
        self._jobs[job_id].next_run_at = self._compute_next_run(self._jobs[job_id].schedule)
        return True

    def list_jobs(self) -> list[AutonomousJob]:
        """Return all jobs (for dashboard)."""
        return list(self._jobs.values())

    def get_job(self, job_id: UUID) -> AutonomousJob | None:
        """Return a job by ID."""
        return self._jobs.get(job_id)

    async def restore_jobs(self, jobs: list[AutonomousJob]) -> int:
        """Restore jobs after a reboot.

        In production, this would replay the event log to find all
        autonomous_job.scheduled events without corresponding
        autonomous_job.completed events.
        """
        count = 0
        for job in jobs:
            if job.status == JobStatus.SCHEDULED:
                job.next_run_at = self._compute_next_run(job.schedule)
                self._jobs[job.id] = job
                count += 1
        _log.info("autonomous_jobs.restored", count=count)
        return count

    async def _loop(self) -> None:
        """Background loop: check for due jobs."""
        while self._running:
            try:
                now = utc_now()
                due = [
                    job
                    for job in self._jobs.values()
                    if job.status == JobStatus.SCHEDULED
                    and job.next_run_at is not None
                    and job.next_run_at <= now
                ]
                for job in due:
                    asyncio.create_task(self._execute_job(job))
            except asyncio.CancelledError:
                break
            except Exception:
                _log.exception("autonomous_jobs.loop_error")
            await asyncio.sleep(self._check_interval_s)

    async def _execute_job(self, job: AutonomousJob) -> None:
        """Execute a job: create a plan and submit it."""
        job.status = JobStatus.RUNNING
        job.last_run_at = utc_now()
        job.run_count += 1

        _log.info(
            "autonomous_jobs.executing",
            job_id=str(job.id),
            name=job.name,
            run_count=job.run_count,
        )

        try:
            # If the job has a pre-built plan, use it
            # Otherwise, the supervisor will create one from the goal
            # For now, just emit an event — the supervisor picks it up
            await self._bus.publish(
                Event(
                    topic="autonomous_job.fired",
                    correlation_id=job.id,
                    actor=ActorRef.system(),
                    payload={
                        "job_id": str(job.id),
                        "name": job.name,
                        "goal": job.goal,
                        "priority": job.priority,
                        "project_id": job.project_id,
                    },
                ),
            )

            job.status = JobStatus.SCHEDULED  # Ready for next run
            job.last_result = "submitted"

            # Check if we should stop
            if job.max_runs is not None and job.run_count >= job.max_runs:
                job.status = JobStatus.COMPLETED
                _log.info("autonomous_jobs.max_runs_reached", job_id=str(job.id))
            elif job.until is not None and utc_now() >= job.until:
                job.status = JobStatus.COMPLETED
                _log.info("autonomous_jobs.until_reached", job_id=str(job.id))
            else:
                job.next_run_at = self._compute_next_run(job.schedule)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.last_error = str(e)
            _log.exception("autonomous_jobs.execution_failed", job_id=str(job.id))

    async def _check_event_triggers(self, event: Event) -> None:
        """Check if any job is triggered by this event."""
        for job in list(self._jobs.values()):
            if (
                job.status == JobStatus.SCHEDULED
                and job.trigger_event is not None
                and event.topic == job.trigger_event
            ):
                asyncio.create_task(self._execute_job(job))

    @staticmethod
    def _compute_next_run(schedule: ScheduleSpec | None) -> datetime | None:
        """Compute the next run time for a schedule."""
        if schedule is None:
            return None
        now = utc_now()
        if schedule.schedule_type == ScheduleType.ONE_TIME:
            if schedule.run_at is not None and schedule.run_at > now:
                return schedule.run_at
            return None
        if schedule.schedule_type == ScheduleType.INTERVAL:
            assert schedule.interval_s is not None
            return now + timedelta(seconds=schedule.interval_s)
        if schedule.schedule_type == ScheduleType.CRON:
            return now + timedelta(minutes=1)  # Simplified — real cron in v2.1
