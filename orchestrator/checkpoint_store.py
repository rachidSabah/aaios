"""In-memory checkpoint store — for tests and ephemeral runs.

Not durable across process restarts. A persistent implementation (backed
by the event store) lands in Phase 8 with the Security Layer.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from orchestrator.contracts.checkpoint import Checkpoint


class InMemoryCheckpointStore:
    """In-memory checkpoint store. Thread-safe via a single lock.

    Checkpoints are stored per task, in sequence order. ``get_latest``
    returns the highest-sequence checkpoint.
    """

    def __init__(self) -> None:
        self._checkpoints: dict[UUID, list[Checkpoint]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint."""
        async with self._lock:
            self._checkpoints[checkpoint.task_id].append(checkpoint)
            # Keep sorted by sequence (they should arrive in order, but be safe)
            self._checkpoints[checkpoint.task_id].sort(key=lambda c: c.sequence)

    async def get_latest(self, task_id: UUID) -> Checkpoint | None:
        """Return the latest checkpoint for ``task_id``, or None."""
        async with self._lock:
            cps = self._checkpoints.get(task_id, [])
            if not cps:
                return None
            return cps[-1]

    async def get_all(self, task_id: UUID) -> list[Checkpoint]:
        """Return all checkpoints for ``task_id``, in sequence order."""
        async with self._lock:
            return list(self._checkpoints.get(task_id, []))

    async def get_at_sequence(self, task_id: UUID, sequence: int) -> Checkpoint | None:
        """Return the checkpoint at the given sequence, or None."""
        async with self._lock:
            for cp in self._checkpoints.get(task_id, []):
                if cp.sequence == sequence:
                    return cp
            return None

    async def list_tasks(self) -> list[UUID]:
        """Return all task IDs that have at least one checkpoint."""
        async with self._lock:
            return list(self._checkpoints.keys())

    async def delete(self, task_id: UUID) -> int:
        """Delete all checkpoints for ``task_id``. Returns count deleted."""
        async with self._lock:
            cps = self._checkpoints.pop(task_id, [])
            return len(cps)
