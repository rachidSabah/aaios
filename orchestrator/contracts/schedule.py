"""Schedule spec — for recurring and delayed task submission."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.timestamp import utc_now

__all__ = ["ScheduleSpec", "ScheduleType"]


class ScheduleType(StrEnum):
    """The kind of schedule."""

    ONE_TIME = "one_time"  # run once at a specific time
    CRON = "cron"  # cron expression
    INTERVAL = "interval"  # every N seconds


class ScheduleSpec(BaseModel):
    """A schedule for a task.

    Exactly one of ``run_at``, ``cron``, or ``interval_s`` must be set,
    matching the ``schedule_type``.

    Examples:
        # Run once in 1 hour
        ScheduleSpec(schedule_type=ScheduleType.ONE_TIME,
                     run_at=utc_now() + timedelta(hours=1))

        # Every weekday at 9am
        ScheduleSpec(schedule_type=ScheduleType.CRON, cron='0 9 * * 1-5')

        # Every hour
        ScheduleSpec(schedule_type=ScheduleType.INTERVAL, interval_s=3600)
    """

    model_config = ConfigDict(frozen=True)

    schedule_type: ScheduleType
    run_at: datetime | None = Field(default=None, description="For ONE_TIME.")
    cron: str | None = Field(default=None, description="For CRON (5-field cron expression).")
    interval_s: float | None = Field(default=None, ge=0.0, description="For INTERVAL.")
    # Optional: stop scheduling after this time
    until: datetime | None = Field(default=None)
    # Optional: max number of runs (None = unlimited)
    max_runs: int | None = Field(default=None, ge=1)

    def validate_spec(self) -> list[str]:
        """Return a list of validation errors (empty if valid)."""
        errors: list[str] = []
        if self.schedule_type == ScheduleType.ONE_TIME and self.run_at is None:
            errors.append("run_at must be set for ONE_TIME schedule")
        if self.schedule_type == ScheduleType.CRON:
            if self.cron is None:
                errors.append("cron must be set for CRON schedule")
            elif not _is_valid_cron(self.cron):
                errors.append(f"invalid cron expression: {self.cron!r}")
        if self.schedule_type == ScheduleType.INTERVAL and self.interval_s is None:
            errors.append("interval_s must be set for INTERVAL schedule")
        if self.run_at is not None and self.run_at < utc_now():
            errors.append("run_at is in the past")
        return errors


def _is_valid_cron(expr: str) -> bool:
    """Basic cron expression validation (5 fields, each parseable).

    This is a simplified check — the real scheduling engine (Windows Task
    Scheduler / APScheduler) does the full validation.
    """
    fields = expr.split()
    if len(fields) != 5:
        return False
    # Each field: digits, *, /, -, or , — accept any non-empty string of these
    allowed = set("0123456789*/-,")
    for f in fields:
        if not f or not all(c in allowed for c in f):
            return False
    return True
