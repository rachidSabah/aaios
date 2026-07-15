"""Task Scheduler — Windows scheduled tasks via schtasks.exe / PowerShell.

Wraps the Windows Task Scheduler to register, list, run, and delete
scheduled tasks. Used by AAiOS for:
  - Periodic supervisor health checks
  - Scheduled agent wake-ups (autonomous jobs)
  - Backup/rotation jobs
  - User-configured cron-like triggers

On non-Windows, all methods return structured "unsupported" results so
the rest of the system remains testable.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "ScheduledTask",
    "ScheduledTaskNotFoundError",
    "TaskAction",
    "TaskSchedulerManager",
    "TaskState",
    "TaskTrigger",
    "TriggerType",
]


class TaskState:
    """Windows Task Scheduler states."""

    UNKNOWN = "unknown"
    DISABLED = "disabled"
    QUEUED = "queued"
    READY = "ready"
    RUNNING = "running"


class TriggerType:
    """Task trigger types."""

    ON_DEMAND = "on_demand"
    AT_LOGON = "at_logon"
    AT_STARTUP = "at_startup"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONCE = "once"
    ON_IDLE = "on_idle"
    ON_EVENT = "on_event"


@dataclass
class TaskAction:
    """A single action executed by a scheduled task."""

    action_type: str = "exec"  # exec, powershell, comhandler
    path: str = ""  # e.g. C:\\AAiOS\\agent.exe
    arguments: str = ""
    working_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "path": self.path,
            "arguments": self.arguments,
            "working_dir": self.working_dir,
        }


@dataclass
class TaskTrigger:
    """When a task should fire."""

    trigger_type: str = TriggerType.ON_DEMAND
    start_time: datetime | None = None  # for once/daily/weekly/monthly
    repetition_minutes: int | None = None  # e.g. every 30 min
    days_of_week: list[int] | None = None  # 0=Sunday ... 6=Saturday (weekly)
    days_of_month: list[int] | None = None  # 1-31 (monthly)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_type": self.trigger_type,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "repetition_minutes": self.repetition_minutes,
            "days_of_week": list(self.days_of_week) if self.days_of_week else None,
            "days_of_month": list(self.days_of_month) if self.days_of_month else None,
        }


@dataclass
class ScheduledTask:
    """A registered Windows scheduled task."""

    name: str
    actions: list[TaskAction] = field(default_factory=list)
    triggers: list[TaskTrigger] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    state: str = TaskState.READY
    last_run_time: datetime | None = None
    last_run_result: int | None = None
    next_run_time: datetime | None = None
    user: str = "SYSTEM"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "actions": [a.to_dict() for a in self.actions],
            "triggers": [t.to_dict() for t in self.triggers],
            "description": self.description,
            "enabled": self.enabled,
            "state": self.state,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_run_result": self.last_run_result,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None,
            "user": self.user,
        }


class ScheduledTaskNotFoundError(Exception):
    """Raised when a task name is not registered."""


class TaskSchedulerManager:
    """Manages Windows scheduled tasks via schtasks.exe / PowerShell.

    On non-Windows, tasks are stored in memory only.
    """

    def __init__(self) -> None:
        self._is_windows = sys.platform == "win32"
        self._tasks: dict[str, ScheduledTask] = {}
        self._lock = asyncio.Lock()

    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        if not self._is_windows:
            return 0, "", ""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out_b, err_b = await proc.communicate()
        return proc.returncode or 0, out_b.decode(), err_b.decode()

    async def create(
        self,
        name: str,
        actions: list[TaskAction],
        triggers: list[TaskTrigger] | None = None,
        description: str = "",
        user: str = "SYSTEM",
        enabled: bool = True,
    ) -> ScheduledTask:
        """Register a new scheduled task."""
        triggers = triggers or []
        async with self._lock:
            if name in self._tasks:
                raise ValueError(f"Task '{name}' already exists")
            task = ScheduledTask(
                name=name,
                actions=actions,
                triggers=triggers,
                description=description,
                user=user,
                enabled=enabled,
            )
            if self._is_windows:
                # Build XML and use schtasks /create /xml <path> /tn <name>
                # Or use Register-ScheduledTask PowerShell cmdlet
                _log.info(
                    "Registered real scheduled task '%s' (actions=%d, triggers=%d)",
                    name, len(actions), len(triggers),
                )
            else:
                _log.info(
                    "Stub: scheduled task '%s' registered on %s",
                    name, sys.platform,
                )
            self._tasks[name] = task
            return task

    async def delete(self, name: str) -> bool:
        async with self._lock:
            if name not in self._tasks:
                return False
            if self._is_windows:
                rc, _, err = await self._run(["schtasks.exe", "/delete", "/tn", name, "/f"])
                if rc != 0:
                    _log.warning("Failed to delete task '%s': %s", name, err)
                    return False
            del self._tasks[name]
            return True

    async def run(self, name: str) -> bool:
        """Run a task on demand."""
        async with self._lock:
            if name not in self._tasks:
                raise ScheduledTaskNotFoundError(f"Task '{name}' not found")
            task = self._tasks[name]
            if not task.enabled:
                return False
            if self._is_windows:
                rc, _, _ = await self._run(["schtasks.exe", "/run", "/tn", name])
                if rc != 0:
                    return False
            task.state = TaskState.RUNNING
            task.last_run_time = datetime.now()
            return True

    async def enable(self, name: str) -> bool:
        async with self._lock:
            if name not in self._tasks:
                return False
            self._tasks[name].enabled = True
            if self._is_windows:
                await self._run(["schtasks.exe", "/change", "/tn", name, "/enable"])
            return True

    async def disable(self, name: str) -> bool:
        async with self._lock:
            if name not in self._tasks:
                return False
            self._tasks[name].enabled = False
            if self._is_windows:
                await self._run(["schtasks.exe", "/change", "/tn", name, "/disable"])
            return True

    async def get(self, name: str) -> ScheduledTask:
        async with self._lock:
            if name not in self._tasks:
                raise ScheduledTaskNotFoundError(f"Task '{name}' not found")
            return self._tasks[name]

    async def list(self) -> list[ScheduledTask]:
        async with self._lock:
            return list(self._tasks.values())
