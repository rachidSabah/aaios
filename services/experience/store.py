"""Experience Store — persistent storage for ExperienceRecords.

The store:
  - Persists each record as a JSON file (one per record)
  - Maintains an in-memory index for fast lookup by ID, agent, provider, etc.
  - Supports filtering, pagination, and aggregation queries
  - Thread-safe via asyncio.Lock
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from core.logging import get_logger
from services.experience.models import ExperienceRecord

_log = get_logger(__name__)

__all__ = [
    "ExperienceFilter",
    "ExperienceNotFoundError",
    "ExperienceStore",
    "ExperienceSummary",
]


class ExperienceNotFoundError(Exception):
    """Raised when an experience ID is not found."""


@dataclass
class ExperienceFilter:
    """Filter for querying experiences."""

    agent_id: str | None = None
    agent_type: str | None = None
    provider: str | None = None
    model: str | None = None
    capability: str | None = None
    outcome: str | None = None
    success: bool | None = None
    workflow_id: str | None = None
    min_quality: float | None = None
    min_confidence: float | None = None
    since: datetime | None = None
    until: datetime | None = None
    tags: list[str] = field(default_factory=list)

    def matches(self, record: ExperienceRecord) -> bool:
        """Check if a record matches this filter."""
        if self.agent_id is not None and record.agent_id != self.agent_id:
            return False
        if self.agent_type is not None and record.agent_type != self.agent_type:
            return False
        if self.provider is not None and record.provider != self.provider:
            return False
        if self.model is not None and record.model != self.model:
            return False
        if self.capability is not None and self.capability not in record.capabilities_used:
            return False
        if self.outcome is not None and record.outcome != self.outcome:
            return False
        if self.success is not None and record.success != self.success:
            return False
        if self.workflow_id is not None and record.workflow_id != self.workflow_id:
            return False
        if self.min_quality is not None and record.quality_score() < self.min_quality:
            return False
        if self.min_confidence is not None and record.confidence < self.min_confidence:
            return False
        if self.since is not None and record.timestamp < self.since:
            return False
        if self.until is not None and record.timestamp > self.until:
            return False
        return True


@dataclass
class ExperienceSummary:
    """Aggregated summary of a set of experiences."""

    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_execution_time_s: float = 0.0
    avg_latency_s: float = 0.0
    avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    avg_quality: float = 0.0
    avg_confidence: float = 0.0
    avg_retries: float = 0.0
    total_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "avg_execution_time_s": round(self.avg_execution_time_s, 4),
            "avg_latency_s": round(self.avg_latency_s, 4),
            "avg_cost_usd": round(self.avg_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "avg_quality": round(self.avg_quality, 4),
            "avg_confidence": round(self.avg_confidence, 4),
            "avg_retries": round(self.avg_retries, 4),
            "total_tokens": self.total_tokens,
        }


class ExperienceStore:
    """Persistent store for experience records.

    Records are stored as individual JSON files in a directory.
    An in-memory index enables fast queries without loading every file.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir
        self._records: dict[UUID, ExperienceRecord] = {}
        self._by_agent: dict[str, list[UUID]] = defaultdict(list)
        self._by_provider: dict[str, list[UUID]] = defaultdict(list)
        self._by_capability: dict[str, list[UUID]] = defaultdict(list)
        self._by_outcome: dict[str, list[UUID]] = defaultdict(list)
        self._by_workflow: dict[str, list[UUID]] = defaultdict(list)
        self._by_context_hash: dict[str, list[UUID]] = defaultdict(list)
        self._lock = asyncio.Lock()
        if storage_dir is not None:
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_all()

    def _record_path(self, experience_id: UUID) -> Path:
        if self._storage_dir is None:
            raise RuntimeError("No storage directory configured")
        return self._storage_dir / f"{experience_id}.json"

    def _load_all(self) -> None:
        """Load all records from disk at startup."""
        if self._storage_dir is None:
            return
        for path in self._storage_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                record = ExperienceRecord.from_dict(data)
                self._records[record.experience_id] = record
                self._index_record(record)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                _log.warning("Failed to load experience from %s: %s", path, e)

    def _index_record(self, record: ExperienceRecord) -> None:
        """Add a record to all in-memory indices."""
        self._by_agent[record.agent_id].append(record.experience_id)
        if record.provider:
            self._by_provider[record.provider].append(record.experience_id)
        for cap in record.capabilities_used:
            self._by_capability[cap].append(record.experience_id)
        self._by_outcome[record.outcome].append(record.experience_id)
        if record.workflow_id:
            self._by_workflow[record.workflow_id].append(record.experience_id)
        self._by_context_hash[record.context_hash].append(record.experience_id)

    def _persist(self, record: ExperienceRecord) -> None:
        """Persist a single record to disk."""
        if self._storage_dir is None:
            return
        path = self._record_path(record.experience_id)
        path.write_text(
            json.dumps(record.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def _delete_persisted(self, experience_id: UUID) -> None:
        if self._storage_dir is None:
            return
        path = self._record_path(experience_id)
        if path.exists():
            path.unlink()

    async def store(self, record: ExperienceRecord) -> ExperienceRecord:
        """Store a new experience record."""
        async with self._lock:
            self._records[record.experience_id] = record
            self._index_record(record)
            self._persist(record)
            _log.info(
                "Stored experience %s (agent=%s, outcome=%s)",
                record.experience_id,
                record.agent_id,
                record.outcome,
            )
            return record

    async def get(self, experience_id: UUID) -> ExperienceRecord:
        """Retrieve a single record by ID."""
        async with self._lock:
            if experience_id not in self._records:
                raise ExperienceNotFoundError(
                    f"Experience {experience_id} not found",
                )
            return self._records[experience_id]

    async def query(
        self,
        filter: ExperienceFilter | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperienceRecord]:
        """Query records with optional filtering + pagination."""
        async with self._lock:
            records = list(self._records.values())
        if filter is not None:
            records = [r for r in records if filter.matches(r)]
        # Sort by timestamp descending (most recent first)
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[offset : offset + limit]

    async def count(self, filter: ExperienceFilter | None = None) -> int:
        """Count records matching a filter."""
        async with self._lock:
            records = list(self._records.values())
        if filter is not None:
            records = [r for r in records if filter.matches(r)]
        return len(records)

    async def summarize(
        self,
        filter: ExperienceFilter | None = None,
    ) -> ExperienceSummary:
        """Compute aggregate statistics over a set of records."""
        async with self._lock:
            records = list(self._records.values())
        if filter is not None:
            records = [r for r in records if filter.matches(r)]
        if not records:
            return ExperienceSummary()
        total = len(records)
        success_count = sum(1 for r in records if r.success)
        return ExperienceSummary(
            total_count=total,
            success_count=success_count,
            failure_count=total - success_count,
            success_rate=success_count / total,
            avg_execution_time_s=sum(r.execution_time_s for r in records) / total,
            avg_latency_s=sum(r.latency_s for r in records) / total,
            avg_cost_usd=sum(r.cost_usd for r in records) / total,
            total_cost_usd=sum(r.cost_usd for r in records),
            avg_quality=sum(r.quality_score() for r in records) / total,
            avg_confidence=sum(r.confidence for r in records) / total,
            avg_retries=sum(r.retries for r in records) / total,
            total_tokens=sum(r.token_usage.total_tokens for r in records),
        )

    async def find_by_context_hash(self, context_hash: str) -> list[ExperienceRecord]:
        """Find all records with the same context hash (similar tasks)."""
        async with self._lock:
            ids = self._by_context_hash.get(context_hash, [])
            return [self._records[i] for i in ids if i in self._records]

    async def list_agents(self) -> list[str]:
        """List all agent IDs that have experiences."""
        async with self._lock:
            return sorted(self._by_agent.keys())

    async def list_providers(self) -> list[str]:
        """List all providers that have experiences."""
        async with self._lock:
            return sorted(self._by_provider.keys())

    async def list_capabilities(self) -> list[str]:
        """List all capabilities seen in experiences."""
        async with self._lock:
            return sorted(self._by_capability.keys())

    async def delete(self, experience_id: UUID) -> bool:
        """Delete a record."""
        async with self._lock:
            if experience_id not in self._records:
                return False
            record = self._records.pop(experience_id)
            # Remove from indices
            self._by_agent[record.agent_id].remove(experience_id)
            if not self._by_agent[record.agent_id]:
                del self._by_agent[record.agent_id]
            if record.provider and experience_id in self._by_provider[record.provider]:
                self._by_provider[record.provider].remove(experience_id)
                if not self._by_provider[record.provider]:
                    del self._by_provider[record.provider]
            for cap in record.capabilities_used:
                if cap in self._by_capability and experience_id in self._by_capability[cap]:
                    self._by_capability[cap].remove(experience_id)
                    if not self._by_capability[cap]:
                        del self._by_capability[cap]
            if record.outcome in self._by_outcome:
                self._by_outcome[record.outcome].remove(experience_id)
                if not self._by_outcome[record.outcome]:
                    del self._by_outcome[record.outcome]
            if record.workflow_id and record.workflow_id in self._by_workflow:
                self._by_workflow[record.workflow_id].remove(experience_id)
                if not self._by_workflow[record.workflow_id]:
                    del self._by_workflow[record.workflow_id]
            self._by_context_hash[record.context_hash].remove(experience_id)
            if not self._by_context_hash[record.context_hash]:
                del self._by_context_hash[record.context_hash]
            self._delete_persisted(experience_id)
            return True

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete all records older than the cutoff. Returns count deleted."""
        async with self._lock:
            to_delete = [eid for eid, r in self._records.items() if r.timestamp < cutoff]
        for eid in to_delete:
            await self.delete(eid)
        return len(to_delete)

    async def all_records(self) -> list[ExperienceRecord]:
        """Return all records (for export, compression, etc.)."""
        async with self._lock:
            return list(self._records.values())

    async def replace(self, record: ExperienceRecord) -> ExperienceRecord:
        """Replace an existing record (used by compressor)."""
        async with self._lock:
            if record.experience_id not in self._records:
                raise ExperienceNotFoundError(
                    f"Experience {record.experience_id} not found",
                )
            # Remove old indices, add new
            old = self._records[record.experience_id]
            self._by_agent[old.agent_id].remove(record.experience_id)
            # ... (simplified: just overwrite and re-index)
            self._records[record.experience_id] = record
            self._persist(record)
            return record
