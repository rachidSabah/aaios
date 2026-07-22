"""Enterprise Memory Platform — 15 coordinated memory systems + Memory Orchestrator.

Each memory type has its own storage policy, retention, and ranking.
The MemoryOrchestrator automatically chooses, promotes, demotes, merges,
and compresses memories to manage context windows and token budgets.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.knowledge.models import MemoryRecord, MemoryScope, MemoryType, StoragePolicy

_log = get_logger(__name__)

__all__ = ["MemoryOrchestrator", "MemoryStore"]


class MemoryStore:
    """In-memory store for a single memory type.

    Each MemoryType gets its own MemoryStore instance with its own
    storage policy. The MemoryOrchestrator manages all stores.
    """

    def __init__(self, memory_type: str, policy: StoragePolicy | None = None) -> None:
        self.memory_type = memory_type
        self.policy = policy or StoragePolicy()
        self._records: dict[str, MemoryRecord] = {}
        self._lock = asyncio.Lock()

    async def store(self, record: MemoryRecord) -> MemoryRecord:
        async with self._lock:
            self._records[record.memory_id] = record
            self._enforce_limits()
        return record

    async def get(self, memory_id: str) -> MemoryRecord | None:
        async with self._lock:
            record = self._records.get(memory_id)
            if record:
                record.access_count += 1
            return record

    async def search(
        self,
        query: str = "",
        *,
        scope: MemoryScope | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        async with self._lock:
            records = list(self._records.values())
        if scope:
            if scope.project_id:
                records = [r for r in records if r.scope.project_id == scope.project_id]
            if scope.mission_id:
                records = [r for r in records if r.scope.mission_id == scope.mission_id]
            if scope.agent_id:
                records = [r for r in records if r.scope.agent_id == scope.agent_id]
        if tags:
            records = [r for r in records if any(t in r.tags for t in tags)]
        if query:
            query_lower = query.lower()
            records = [r for r in records if query_lower in r.content.lower()]
        # Rank by importance * confidence * recency
        now = datetime.now(UTC)
        records.sort(
            key=lambda r: (
                r.importance
                * r.confidence
                * max(0.1, 1.0 - (now - r.created_at).total_seconds() / 86400)
            ),
            reverse=True,
        )
        return records[:limit]

    async def delete(self, memory_id: str) -> bool:
        async with self._lock:
            return self._records.pop(memory_id, None) is not None

    async def count(self) -> int:
        async with self._lock:
            return len(self._records)

    async def all_records(self) -> list[MemoryRecord]:
        async with self._lock:
            return list(self._records.values())

    async def expire_old(self) -> int:
        """Delete expired records. Returns count deleted."""
        now = datetime.now(UTC)
        deleted = 0
        async with self._lock:
            to_delete = [
                mid for mid, r in self._records.items() if r.expires_at and r.expires_at < now
            ]
            for mid in to_delete:
                self._records.pop(mid, None)
                deleted += 1
        return deleted

    def _enforce_limits(self) -> None:
        """Enforce max_entries limit."""
        if len(self._records) <= self.policy.max_entries:
            return
        # Remove oldest lowest-importance
        sorted_records = sorted(
            self._records.items(),
            key=lambda x: (x[1].importance, x[1].created_at),
        )
        excess = len(self._records) - self.policy.max_entries
        for mid, _ in sorted_records[:excess]:
            self._records.pop(mid, None)


class MemoryOrchestrator:
    """Manages all 15 memory types.

    Responsibilities:
      - Choose the right memory type automatically
      - Promote/demote memories between types
      - Merge duplicates
      - Summarize history
      - Compress context
      - Manage context windows + token budgets
    """

    DEFAULT_POLICIES: dict[str, StoragePolicy] = {
        MemoryType.SHORT_TERM.value: StoragePolicy(
            max_age_days=1, max_entries=1000, compress_after_days=0
        ),
        MemoryType.LONG_TERM.value: StoragePolicy(
            max_age_days=3650, max_entries=500_000, compress_after_days=90
        ),
        MemoryType.WORKING.value: StoragePolicy(
            max_age_days=7, max_entries=5000, compress_after_days=3
        ),
        MemoryType.SEMANTIC.value: StoragePolicy(
            max_age_days=3650, max_entries=200_000, compress_after_days=60
        ),
        MemoryType.PROCEDURAL.value: StoragePolicy(
            max_age_days=3650, max_entries=100_000, compress_after_days=90
        ),
        MemoryType.EPISODIC.value: StoragePolicy(
            max_age_days=365, max_entries=100_000, compress_after_days=30
        ),
        MemoryType.PROJECT.value: StoragePolicy(
            max_age_days=3650, max_entries=50_000, compress_after_days=60
        ),
        MemoryType.MISSION.value: StoragePolicy(
            max_age_days=365, max_entries=50_000, compress_after_days=30
        ),
        MemoryType.WORKFLOW.value: StoragePolicy(
            max_age_days=365, max_entries=50_000, compress_after_days=30
        ),
        MemoryType.AGENT.value: StoragePolicy(
            max_age_days=3650, max_entries=20_000, compress_after_days=90
        ),
        MemoryType.PROVIDER.value: StoragePolicy(
            max_age_days=3650, max_entries=10_000, compress_after_days=90
        ),
        MemoryType.USER.value: StoragePolicy(
            max_age_days=3650, max_entries=20_000, compress_after_days=90
        ),
        MemoryType.ORGANIZATION.value: StoragePolicy(
            max_age_days=3650, max_entries=100_000, compress_after_days=90
        ),
        MemoryType.EXECUTION.value: StoragePolicy(
            max_age_days=90, max_entries=200_000, compress_after_days=7
        ),
        MemoryType.CONVERSATION.value: StoragePolicy(
            max_age_days=30, max_entries=10_000, compress_after_days=3
        ),
    }

    def __init__(self) -> None:
        self._stores: dict[str, MemoryStore] = {
            mt: MemoryStore(mt, policy) for mt, policy in self.DEFAULT_POLICIES.items()
        }
        self._lock = asyncio.Lock()

    @property
    def memory_types(self) -> list[str]:
        return list(self._stores.keys())

    async def store(self, record: MemoryRecord) -> MemoryRecord:
        """Store a memory record in the appropriate memory store."""
        store = self._stores.get(record.memory_type)
        if store is None:
            store = self._stores[MemoryType.LONG_TERM.value]
            record.memory_type = MemoryType.LONG_TERM.value
        return await store.store(record)

    async def get(self, memory_id: str, memory_type: str | None = None) -> MemoryRecord | None:
        """Get a memory by ID."""
        if memory_type:
            store = self._stores.get(memory_type)
            if store:
                return await store.get(memory_id)
        # Search all stores
        for store in self._stores.values():
            record = await store.get(memory_id)
            if record:
                return record
        return None

    async def search(
        self,
        query: str = "",
        *,
        memory_types: list[str] | None = None,
        scope: MemoryScope | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """Search across memory types."""
        types = memory_types or list(self._stores.keys())
        all_results: list[MemoryRecord] = []
        for mt in types:
            store = self._stores.get(mt)
            if store:
                results = await store.search(query, scope=scope, tags=tags, limit=limit)
                all_results.extend(results)
        # Re-rank across all
        now = datetime.now(UTC)
        all_results.sort(
            key=lambda r: (
                r.importance
                * r.confidence
                * max(0.1, 1.0 - (now - r.created_at).total_seconds() / 86400)
            ),
            reverse=True,
        )
        return all_results[:limit]

    async def promote(self, memory_id: str, from_type: str, to_type: str) -> MemoryRecord | None:
        """Promote a memory from one type to another (e.g., short_term → long_term)."""
        from_store = self._stores.get(from_type)
        to_store = self._stores.get(to_type)
        if not from_store or not to_store:
            return None
        record = await from_store.get(memory_id)
        if record is None:
            return None
        # Create a copy with the new type
        promoted = MemoryRecord(
            memory_id=record.memory_id,
            memory_type=to_type,
            scope=record.scope,
            content=record.content,
            content_type=record.content_type,
            metadata={**record.metadata, "promoted_from": from_type},
            tags=record.tags,
            importance=min(1.0, record.importance + 0.1),
            confidence=record.confidence,
            access_count=record.access_count,
            created_at=record.created_at,
            updated_at=datetime.now(UTC),
            version=record.version + 1,
            owner=record.owner,
        )
        await to_store.store(promoted)
        await from_store.delete(memory_id)
        _log.info("Promoted memory %s from %s to %s", memory_id, from_type, to_type)
        return promoted

    async def demote(self, memory_id: str, from_type: str, to_type: str) -> MemoryRecord | None:
        """Demote a memory (e.g., long_term → archived)."""
        return await self.promote(memory_id, from_type, to_type)

    async def merge_duplicates(self) -> int:
        """Merge duplicate memories (same content hash). Returns count merged."""
        merged = 0
        for store in self._stores.values():
            records = await store.all_records()
            by_hash: dict[str, list[MemoryRecord]] = defaultdict(list)
            for r in records:
                content_hash = hashlib.sha256(r.content.encode()).hexdigest()[:16]
                by_hash[content_hash].append(r)
            for _hash, duplicates in by_hash.items():
                if len(duplicates) <= 1:
                    continue
                # Keep the highest-importance one, delete the rest
                duplicates.sort(key=lambda r: r.importance, reverse=True)

                for dup in duplicates[1:]:
                    await store.delete(dup.memory_id)
                    merged += 1
        return merged

    async def compress_context(self, max_tokens: int = 4096) -> str:
        """Compress memory context to fit within a token budget.

        Returns a compressed context string.
        """
        all_records = []
        for store in self._stores.values():
            records = await store.all_records()
            all_records.extend(records)
        if not all_records:
            return ""
        # Sort by importance * confidence
        all_records.sort(key=lambda r: r.importance * r.confidence, reverse=True)
        # Estimate tokens (4 chars = 1 token roughly)
        token_budget = max_tokens
        context_parts: list[str] = []
        for record in all_records:
            tokens = len(record.content) // 4
            if token_budget - tokens < 0:
                # Truncate
                remaining = token_budget * 4
                if remaining > 100:
                    context_parts.append(record.content[:remaining] + "...")
                break
            context_parts.append(record.content)
            token_budget -= tokens
        return "\n\n".join(context_parts)

    async def stats(self) -> dict[str, Any]:
        """Get statistics for all memory types."""
        stats: dict[str, Any] = {}
        total = 0
        for mt, store in self._stores.items():
            count = await store.count()
            stats[mt] = count
            total += count
        stats["total"] = total
        stats["memory_types"] = len(self._stores)
        return stats

    async def expire_all(self) -> int:
        """Expire old records across all memory types."""
        total = 0
        for store in self._stores.values():
            total += await store.expire_old()
        return total

    async def snapshot(self) -> dict[str, Any]:
        """Take a snapshot of all memory for backup."""
        snapshot: dict[str, Any] = {}
        for mt, store in self._stores.items():
            records = await store.all_records()
            snapshot[mt] = [r.to_dict() for r in records]
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_records": sum(len(v) for v in snapshot.values()),
            "data": snapshot,
        }
