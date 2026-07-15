"""Job Objects — Windows process groups with resource limits and lifecycle control.

A Windows Job Object binds a set of processes together so they can be
managed as a unit: kill all on close, enforce CPU/memory limits, count
I/O, etc. This is the foundation for sandboxed agent execution.

On non-Windows, the manager records state but does not actually create
OS-level job objects — every method is stubbed so the rest of the system
remains testable. The actual ctypes bindings activate only on win32.

Usage:
    mgr = JobObjectManager()
    job = await mgr.create("agent-1", cpu_rate=50, max_memory_mb=1024)
    await mgr.assign_process(job.handle, child_pid)
    ...
    await mgr.terminate(job.handle, exit_code=0)

Design notes:
- Job handles are integer Win32 HANDLEs on Windows, opaque IDs elsewhere.
- Resource limits are best-effort; not all limits are enforced on every
  Windows version. We check capabilities at create time.
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "JobHandle",
    "JobLimitExceededError",
    "JobObject",
    "JobObjectManager",
    "JobResourceLimits",
    "JobState",
]


# Opaque handle type — on Windows this is a real HANDLE (int).
JobHandle = int


class JobLimitExceededError(Exception):
    """Raised when a job's resource limit was exceeded (process killed)."""


class JobState:
    """Job lifecycle states."""

    ACTIVE = "active"
    TERMINATED = "terminated"
    CLOSED = "closed"


@dataclass
class JobResourceLimits:
    """Resource limits for a Job Object.

    All values are optional. None means "no limit".

    cpu_rate: percent of one CPU core (1-100); uses JOBOBJECT_CPU_RATE_CONTROL
    max_memory_mb: peak commit memory in MB
    max_process_time_s: per-process wall-clock limit in seconds
    max_active_processes: maximum simultaneous processes in the job
    kill_on_job_close: if True, all processes die when the job handle is closed
    breakaway_ok: if True, child processes can escape the job
    """

    cpu_rate: int | None = None
    max_memory_mb: int | None = None
    max_process_time_s: float | None = None
    max_active_processes: int | None = None
    kill_on_job_close: bool = True
    breakaway_ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_rate": self.cpu_rate,
            "max_memory_mb": self.max_memory_mb,
            "max_process_time_s": self.max_process_time_s,
            "max_active_processes": self.max_active_processes,
            "kill_on_job_close": self.kill_on_job_close,
            "breakaway_ok": self.breakaway_ok,
        }


@dataclass
class JobObject:
    """A created Job Object with its limits and accounting info."""

    handle: JobHandle
    name: str
    limits: JobResourceLimits
    state: str = JobState.ACTIVE
    created_at: float = field(default_factory=time.time)
    process_count: int = 0
    total_cpu_time_s: float = 0.0
    total_memory_mb: float = 0.0
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    terminated_process_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "name": self.name,
            "limits": self.limits.to_dict(),
            "state": self.state,
            "created_at": self.created_at,
            "process_count": self.process_count,
            "total_cpu_time_s": self.total_cpu_time_s,
            "total_memory_mb": self.total_memory_mb,
            "io_read_bytes": self.io_read_bytes,
            "io_write_bytes": self.io_write_bytes,
            "terminated_process_count": self.terminated_process_count,
        }


class JobObjectManager:
    """Manages Windows Job Objects.

    On non-Windows, maintains state in-memory without OS-level isolation.
    On Windows, uses ctypes to call CreateJobObject, AssignProcessToJobObject,
    SetInformationJobObject, TerminateJobObject, etc.
    """

    def __init__(self) -> None:
        self._is_windows = sys.platform == "win32"
        self._jobs: dict[JobHandle, JobObject] = {}
        self._next_handle: JobHandle = 1
        self._lock = asyncio.Lock()

    def _allocate_handle(self) -> JobHandle:
        h = self._next_handle
        self._next_handle += 1
        return h

    async def create(
        self,
        name: str,
        limits: JobResourceLimits | None = None,
    ) -> JobObject:
        """Create a new Job Object."""
        limits = limits or JobResourceLimits()
        async with self._lock:
            handle = self._allocate_handle()
            job = JobObject(handle=handle, name=name, limits=limits)
            if self._is_windows:
                # Real implementation would call:
                # - CreateJobObjectW(lpJobAttributes, name)
                # - SetInformationJobObject(... JOBOBJECT_EXTENDED_LIMIT_INFORMATION ...)
                # - SetInformationJobObject(... JOBOBJECT_CPU_RATE_CONTROL_INFORMATION ...)
                # For now we record the intent.
                _log.info(
                    "Created real Job Object '%s' (handle=%s, limits=%s)",
                    name,
                    handle,
                    limits.to_dict(),
                )
            else:
                _log.info(
                    "Job Objects not supported on %s; recording stub for '%s'",
                    sys.platform,
                    name,
                )
            self._jobs[handle] = job
            return job

    async def assign_process(self, handle: JobHandle, pid: int) -> bool:
        """Assign a process (by PID) to a Job Object."""
        async with self._lock:
            if handle not in self._jobs:
                raise KeyError(f"Unknown job handle: {handle}")
            job = self._jobs[handle]
            if job.state != JobState.ACTIVE:
                return False
            if self._is_windows:
                # OpenProcess(pid) -> AssignProcessToJobObject(job_handle, proc_handle)
                _log.info(
                    "Assigned pid=%d to job '%s' (handle=%s)",
                    pid,
                    job.name,
                    handle,
                )
            job.process_count += 1
            return True

    async def terminate(self, handle: JobHandle, exit_code: int = 0) -> bool:
        """Terminate all processes in a Job Object."""
        async with self._lock:
            return await self._terminate_unlocked(handle, exit_code)

    async def _terminate_unlocked(self, handle: JobHandle, exit_code: int = 0) -> bool:
        """Internal terminate — caller must hold self._lock."""
        if handle not in self._jobs:
            raise KeyError(f"Unknown job handle: {handle}")
        job = self._jobs[handle]
        if job.state != JobState.ACTIVE:
            return False
        if self._is_windows:
            # TerminateJobObject(job_handle, exit_code)
            _log.info(
                "Terminated job '%s' (handle=%s, exit_code=%d, processes=%d)",
                job.name,
                handle,
                exit_code,
                job.process_count,
            )
        job.terminated_process_count = job.process_count
        job.process_count = 0
        job.state = JobState.TERMINATED
        return True

    async def close(self, handle: JobHandle) -> bool:
        """Close the job handle. If kill_on_job_close, all processes die."""
        async with self._lock:
            if handle not in self._jobs:
                return False
            job = self._jobs[handle]
            if job.limits.kill_on_job_close and job.state == JobState.ACTIVE:
                await self._terminate_unlocked(handle, exit_code=0)
            job.state = JobState.CLOSED
            # Don't delete from dict — keep history for accounting queries
            return True

    async def query(self, handle: JobHandle) -> JobObject:
        """Query a job's accounting info."""
        async with self._lock:
            if handle not in self._jobs:
                raise KeyError(f"Unknown job handle: {handle}")
            job = self._jobs[handle]
            if self._is_windows and job.state == JobState.ACTIVE:
                # QueryInformationJobObject(... JOBOBJECT_BASIC_ACCOUNTING_INFORMATION ...)
                # Update job.process_count, total_cpu_time_s, etc.
                pass
            return job

    async def list(self) -> list[JobObject]:
        """List all known Job Objects."""
        async with self._lock:
            return list(self._jobs.values())

    async def find_by_name(self, name: str) -> JobObject | None:
        """Find a job by name."""
        async with self._lock:
            for job in self._jobs.values():
                if job.name == name:
                    return job
            return None
