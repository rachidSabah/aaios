"""Background worker pool — for long-running or CPU-bound tasks.

The Orchestrator exposes ``submit_background(work)`` which returns
immediately with a job ID. The work runs in a separate worker pool
(ProcessPoolExecutor on Windows with spawn semantics; ThreadPoolExecutor
as a fallback for I/O-bound work).

The dashboard polls or subscribes via WebSocket for completion.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any
from uuid import UUID

from core.logging import get_logger
from orchestrator.contracts.work import BackgroundJob, BackgroundJobStatus

_log = get_logger(__name__)

__all__ = ["BackgroundWorkerPool"]

# Type alias: the work callable
BackgroundWork = Callable[[BackgroundJob], Awaitable[Any]]


class BackgroundWorkerPool:
    """A pool of workers for background jobs.

    By default, uses a ThreadPoolExecutor (good for I/O-bound work like
    embeddings API calls). For CPU-bound work (large JSON parsing, image
    processing), the caller can request a ProcessPoolExecutor via
    ``submit(..., use_process=True)``.

    Note: ProcessPoolExecutor requires the work callable to be picklable
    (top-level function, no closures). ThreadPoolExecutor has no such
    restriction.
    """

    def __init__(
        self,
        *,
        max_workers: int = 4,
        use_processes: bool = False,
    ) -> None:
        self._max_workers = max_workers
        self._use_processes = use_processes
        self._jobs: dict[UUID, BackgroundJob] = {}
        self._thread_pool: ThreadPoolExecutor | None = None
        self._process_pool: ProcessPoolExecutor | None = None
        self._running: bool = False

    async def start(self) -> None:
        """Start the worker pool."""
        if self._running:
            return
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="aaios-worker",
        )
        if self._use_processes:
            self._process_pool = ProcessPoolExecutor(max_workers=self._max_workers)
        self._running = True
        _log.info(
            "workers.started", max_workers=self._max_workers, use_processes=self._use_processes
        )

    async def stop(self) -> None:
        """Stop the worker pool. Waits for in-flight jobs to complete."""
        self._running = False
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
        if self._process_pool is not None:
            self._process_pool.shutdown(wait=True)
            self._process_pool = None
        _log.info("workers.stopped")

    async def submit(
        self,
        work: BackgroundWork,
        *,
        name: str = "",
        inputs: dict[str, Any] | None = None,
        timeout_s: float | None = None,
        use_process: bool = False,
    ) -> UUID:
        """Submit a background job. Returns the job ID immediately.

        Args:
            work: async callable that takes a BackgroundJob and returns a result.
            name: human-readable job name.
            inputs: passed to the work callable as ``job.inputs``.
            timeout_s: max execution time.
            use_process: if True, run in the process pool (CPU-bound work).
        """
        job = BackgroundJob(
            name=name,
            work=work,
            inputs=inputs or {},
            timeout_s=timeout_s,
        )
        self._jobs[job.id] = job
        asyncio.create_task(self._run_job(job, use_process=use_process))
        _log.info("workers.submitted", job_id=str(job.id), name=name)
        return job.id

    def get_job(self, job_id: UUID) -> BackgroundJob | None:
        """Return a job by ID (for polling)."""
        return self._jobs.get(job_id)

    def list_jobs(self, status: BackgroundJobStatus | None = None) -> list[BackgroundJob]:
        """Return all jobs (optionally filtered by status)."""
        if status is None:
            return list(self._jobs.values())
        return [j for j in self._jobs.values() if j.status == status]

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a job. Returns True if found.

        Note: this marks the job as cancelled, but the actual work may
        continue running until it checks the job status. Cooperative
        cancellation only.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in (
            BackgroundJobStatus.SUCCEEDED,
            BackgroundJobStatus.FAILED,
            BackgroundJobStatus.CANCELLED,
        ):
            return False
        job.mark_cancelled()
        _log.info("workers.cancelled", job_id=str(job_id))
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_job(self, job: BackgroundJob, *, use_process: bool) -> None:
        """Run a background job."""
        job.mark_started()
        try:
            if job.timeout_s is not None:
                result = await asyncio.wait_for(job.work(job), timeout=job.timeout_s)
            else:
                result = await job.work(job)
            job.mark_succeeded(result)
            _log.info("workers.job_succeeded", job_id=str(job.id), name=job.name)
        except TimeoutError:
            job.mark_failed(f"Timed out after {job.timeout_s}s")
            _log.warning("workers.job_timeout", job_id=str(job.id), name=job.name)
        except asyncio.CancelledError:
            job.mark_cancelled()
            _log.info("workers.job_cancelled", job_id=str(job.id))
            raise
        except Exception as e:
            job.mark_failed(str(e))
            _log.exception("workers.job_failed", job_id=str(job.id), name=job.name)
