"""Experience Exporter, Compressor, Retention Manager — lifecycle utilities.

Exporter: export experiences to JSON/CSV for external analysis.
Compressor: merge similar experiences into summary records (reduces storage).
RetentionManager: enforce retention policies (delete old records).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from services.experience.models import ExperienceRecord
from services.experience.store import ExperienceFilter, ExperienceStore

_log = get_logger(__name__)

__all__ = [
    "CompressedExperience",
    "ExperienceCompressor",
    "ExperienceExporter",
    "ExperienceRetentionManager",
    "RetentionPolicy",
]


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class ExperienceExporter:
    """Exports experiences to JSON or CSV."""

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store

    async def export_json(
        self,
        filter: ExperienceFilter | None = None,
        *,
        limit: int = 10000,
    ) -> str:
        """Export experiences as a JSON array string."""
        records = await self._store.query(filter, limit=limit)
        return json.dumps(
            [r.to_dict() for r in records],
            indent=2,
            default=str,
        )

    async def export_csv(
        self,
        filter: ExperienceFilter | None = None,
        *,
        limit: int = 10000,
    ) -> str:
        """Export experiences as CSV string."""
        records = await self._store.query(filter, limit=limit)
        if not records:
            return ""
        output = io.StringIO()
        writer = csv.writer(output)
        # Header
        writer.writerow([
            "experience_id", "timestamp", "task_id", "agent_id", "agent_type",
            "provider", "model", "capabilities", "goal", "outcome", "success",
            "execution_time_s", "latency_s", "cost_usd", "tokens_total",
            "reflection_score", "qa_score", "quality_score", "confidence",
            "retries", "failure_reason", "recovery_action",
        ])
        for r in records:
            writer.writerow([
                r.experience_id, r.timestamp.isoformat(), r.task_id,
                r.agent_id, r.agent_type, r.provider or "", r.model or "",
                ";".join(r.capabilities_used),
                r.goal[:200], r.outcome, r.success,
                r.execution_time_s, r.latency_s, r.cost_usd,
                r.token_usage.total_tokens,
                r.reflection_score, r.qa_score, r.quality_score(),
                r.confidence, r.retries,
                r.failure_reason or "", r.recovery_action or "",
            ])
        return output.getvalue()

    async def export_summary_json(
        self,
        filter: ExperienceFilter | None = None,
    ) -> str:
        """Export just the summary statistics."""
        summary = await self._store.summarize(filter)
        return json.dumps(summary.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------


from dataclasses import dataclass, field  # noqa: E402


@dataclass
class CompressedExperience:
    """A compressed summary of multiple similar experiences."""

    context_hash: str
    goal: str
    agent_id: str
    capability: str
    experience_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_execution_time_s: float = 0.0
    avg_cost_usd: float = 0.0
    avg_quality: float = 0.0
    representative_id: str | None = None  # the kept record
    merged_ids: list[str] = field(default_factory=list)
    compressed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_hash": self.context_hash,
            "goal": self.goal,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "experience_count": self.experience_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_execution_time_s": round(self.avg_execution_time_s, 4),
            "avg_cost_usd": round(self.avg_cost_usd, 6),
            "avg_quality": round(self.avg_quality, 4),
            "representative_id": self.representative_id,
            "merged_ids": list(self.merged_ids),
            "compressed_at": self.compressed_at,
        }


class ExperienceCompressor:
    """Compresses similar experiences into summary records.

    Groups experiences by (context_hash, agent_id, capability) and keeps
    only the most representative one, replacing the rest with a single
    CompressedExperience summary.

    This reduces storage for repeated similar tasks while preserving the
    statistical signal.
    """

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store

    async def compress(
        self,
        *,
        min_group_size: int = 5,
        max_age_days: int = 30,
    ) -> list[CompressedExperience]:
        """Compress similar experiences. Returns the compressed summaries."""
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        all_records = await self._store.all_records()
        # Group by (context_hash, agent_id, first_capability)
        groups: dict[tuple[str, str, str], list[ExperienceRecord]] = {}
        for r in all_records:
            if r.timestamp < cutoff:
                continue
            cap = r.capabilities_used[0] if r.capabilities_used else "unknown"
            key = (r.context_hash, r.agent_id, cap)
            groups.setdefault(key, []).append(r)

        summaries: list[CompressedExperience] = []
        for key, records in groups.items():
            if len(records) < min_group_size:
                continue
            # Keep the most recent successful one as representative
            successful = [r for r in records if r.success]
            representative = max(
                successful or records,
                key=lambda r: (r.quality_score(), r.timestamp),
            )
            # Delete the rest
            merged_ids: list[str] = []
            for r in records:
                if r.experience_id != representative.experience_id:
                    await self._store.delete(r.experience_id)
                    merged_ids.append(str(r.experience_id))
            summary = CompressedExperience(
                context_hash=key[0],
                goal=representative.goal,
                agent_id=key[1],
                capability=key[2],
                experience_count=len(records),
                success_count=sum(1 for r in records if r.success),
                success_rate=sum(1 for r in records if r.success) / len(records),
                avg_execution_time_s=sum(r.execution_time_s for r in records) / len(records),
                avg_cost_usd=sum(r.cost_usd for r in records) / len(records),
                avg_quality=sum(r.quality_score() for r in records) / len(records),
                representative_id=str(representative.experience_id),
                merged_ids=merged_ids,
                compressed_at=datetime.now(UTC).isoformat(),
            )
            summaries.append(summary)
        _log.info("Compressed %d experience groups", len(summaries))
        return summaries


# ---------------------------------------------------------------------------
# Retention Manager
# ---------------------------------------------------------------------------


@dataclass
class RetentionPolicy:
    """Retention policy for experiences.

    Keeps experiences for `max_age_days`, then deletes them. Optionally
    compresses them first (keeping only summary stats).
    """

    max_age_days: int = 90
    compress_before_delete: bool = True
    min_success_count_to_keep: int = 1  # keep at least N successes per context_hash
    max_total_records: int = 100_000


class ExperienceRetentionManager:
    """Enforces retention policies on the experience store."""

    def __init__(
        self,
        store: ExperienceStore,
        *,
        policy: RetentionPolicy | None = None,
    ) -> None:
        self._store = store
        self._policy = policy or RetentionPolicy()
        self._compressor = ExperienceCompressor(store)

    async def enforce(self) -> dict[str, Any]:
        """Enforce the retention policy. Returns a summary of actions taken."""
        actions: dict[str, Any] = {
            "policy": {
                "max_age_days": self._policy.max_age_days,
                "compress_before_delete": self._policy.compress_before_delete,
                "max_total_records": self._policy.max_total_records,
            },
            "started_at": datetime.now(UTC).isoformat(),
            "compressed_groups": 0,
            "deleted_old": 0,
            "deleted_over_limit": 0,
            "remaining_count": 0,
        }

        # Step 1: Compress old similar experiences
        if self._policy.compress_before_delete:
            try:
                summaries = await self._compressor.compress(
                    max_age_days=self._policy.max_age_days,
                )
                actions["compressed_groups"] = len(summaries)
            except Exception as e:
                _log.warning("Compression failed: %s", e)

        # Step 2: Delete records older than max_age_days
        cutoff = datetime.now(UTC) - timedelta(days=self._policy.max_age_days)
        deleted_old = await self._store.delete_older_than(cutoff)
        actions["deleted_old"] = deleted_old

        # Step 3: Enforce max_total_records (delete oldest if over limit)
        current_count = await self._store.count()
        if current_count > self._policy.max_total_records:
            to_delete = current_count - self._policy.max_total_records
            all_records = await self._store.all_records()
            # Sort oldest first
            all_records.sort(key=lambda r: r.timestamp)
            for r in all_records[:to_delete]:
                await self._store.delete(r.experience_id)
            actions["deleted_over_limit"] = to_delete

        actions["remaining_count"] = await self._store.count()
        actions["finished_at"] = datetime.now(UTC).isoformat()
        return actions
