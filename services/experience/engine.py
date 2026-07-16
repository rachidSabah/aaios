"""LearningEngine — top-level facade for the Experience & Learning Engine.

Wires together all subsystems:
  - ExperienceStore (persistence)
  - ExperienceCollector (event-bus subscriber)
  - ExperienceIndexer + ExperienceRetriever (semantic search)
  - ExperienceAnalyzer + ExperienceScorer (patterns + reliability)
  - ExperienceReplayer (replay past executions)
  - ExperienceExporter (JSON/CSV export)
  - ExperienceCompressor + ExperienceRetentionManager (lifecycle)

Usage:
    engine = LearningEngine(storage_dir=Path("/var/lib/aaios/experience"))
    await engine.start(bus)  # subscribes collector to event bus
    # ... tasks run, experiences accumulate ...
    stats = await engine.learning_stats()
    results = await engine.search("python debugging")
    recommendation = await engine.recommend_agent_for_capability("code.generate")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from core.event_bus import EventBus
from core.logging import get_logger
from services.experience.analyzer import (
    ExperienceAnalyzer,
    ExperienceScorer,
    LearningStats,
    PatternReport,
)
from services.experience.collector import ExperienceCollector
from services.experience.lifecycle import (
    ExperienceCompressor,
    ExperienceExporter,
    ExperienceRetentionManager,
    RetentionPolicy,
)
from services.experience.models import ExperienceRecord
from services.experience.replayer import ExperienceReplayer, ReplayMode, ReplayResult
from services.experience.retriever import (
    ExperienceIndexer,
    ExperienceRetriever,
    SearchResult,
    SearchType,
)
from services.experience.store import (
    ExperienceFilter,
    ExperienceNotFoundError,
    ExperienceStore,
    ExperienceSummary,
)

_log = get_logger(__name__)

__all__ = [
    "LearningEngine",
    "ExperienceFilter",
    "ExperienceNotFoundError",
    "ExperienceStore",
    "ExperienceSummary",
    "LearningStats",
    "PatternReport",
    "ReplayMode",
    "ReplayResult",
    "SearchResult",
    "SearchType",
]


class LearningEngine:
    """Top-level facade for the Experience & Learning Engine.

    Call `start()` once at boot to subscribe the collector to the event bus.
    After that, every task lifecycle event generates an experience record
    automatically.
    """

    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        retention_policy: RetentionPolicy | None = None,
    ) -> None:
        self.store = ExperienceStore(storage_dir=storage_dir)
        self.collector = ExperienceCollector(self.store)
        self.indexer = ExperienceIndexer(self.store)
        self.retriever = ExperienceRetriever(self.store, self.indexer)
        self.analyzer = ExperienceAnalyzer(self.store)
        self.scorer = ExperienceScorer(self.store)
        self.replayer = ExperienceReplayer(self.store)
        self.exporter = ExperienceExporter(self.store)
        self.compressor = ExperienceCompressor(self.store)
        self.retention = ExperienceRetentionManager(
            self.store, policy=retention_policy or RetentionPolicy(),
        )
        self._started = False

    async def start(self, bus: EventBus | None = None) -> None:
        """Start the learning engine. Subscribes collector if bus provided."""
        if self._started:
            return
        if bus is not None:
            await self.collector.subscribe(bus)
        # Build initial index from existing records
        await self.indexer.rebuild()
        self._started = True
        _log.info("LearningEngine started")

    async def stop(self) -> None:
        """Stop the learning engine."""
        self._started = False
        _log.info("LearningEngine stopped")

    # --- Convenience methods ---

    async def record(self, record: ExperienceRecord) -> ExperienceRecord:
        """Manually record an experience."""
        stored = await self.store.store(record)
        # Rebuild index incrementally (for simplicity, rebuild on next search)
        return stored

    async def get(self, experience_id: UUID) -> ExperienceRecord:
        """Get an experience by ID."""
        return await self.store.get(experience_id)

    async def list_experiences(
        self,
        filter: ExperienceFilter | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExperienceRecord]:
        """List experiences with optional filtering."""
        return await self.store.query(filter, limit=limit, offset=offset)

    async def search(
        self,
        query: str,
        *,
        search_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search experiences."""
        return await self.retriever.search(query, search_type=search_type, limit=limit)

    async def replay(
        self,
        experience_id: UUID,
        *,
        mode: str = ReplayMode.DRY_RUN,
        comparison_agent_id: str | None = None,
    ) -> ReplayResult:
        """Replay an experience."""
        return await self.replayer.replay(
            experience_id, mode=mode, comparison_agent_id=comparison_agent_id,
        )

    async def learning_stats(self) -> LearningStats:
        """Get top-level learning statistics."""
        return await self.analyzer.learning_stats()

    async def discover_patterns(self) -> PatternReport:
        """Discover success/failure patterns."""
        return await self.analyzer.discover_patterns()

    async def trends(
        self,
        *,
        days: int = 30,
        bucket: str = "day",
    ) -> list[dict[str, Any]]:
        """Get success rate trend over time."""
        return await self.analyzer.trend_over_time(days=days, bucket=bucket)

    async def rank_agents(self, limit: int = 10) -> list[dict[str, Any]]:
        """Rank agents by reliability."""
        scored = await self.scorer.rank_agents(limit=limit)
        return [a.to_dict() for a in scored]

    async def rank_providers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Rank providers by reliability."""
        scored = await self.scorer.rank_providers(limit=limit)
        return [p.to_dict() for p in scored]

    async def rank_capabilities(self, limit: int = 20) -> list[dict[str, Any]]:
        """Rank capabilities by success rate."""
        scored = await self.scorer.rank_capabilities(limit=limit)
        return [c.to_dict() for c in scored]

    async def rank_workflows(self, limit: int = 10) -> list[dict[str, Any]]:
        """Rank workflows by quality."""
        return await self.retriever.highest_quality_workflows(limit=limit)

    async def recommend_agent_for_capability(
        self,
        capability: str,
    ) -> dict[str, Any] | None:
        """Recommend the best agent for a capability."""
        return await self.scorer.recommend_agent_for_capability(capability)

    async def export_json(
        self,
        filter: ExperienceFilter | None = None,
        *,
        limit: int = 10000,
    ) -> str:
        """Export experiences as JSON."""
        return await self.exporter.export_json(filter, limit=limit)

    async def export_csv(
        self,
        filter: ExperienceFilter | None = None,
        *,
        limit: int = 10000,
    ) -> str:
        """Export experiences as CSV."""
        return await self.exporter.export_csv(filter, limit=limit)

    async def enforce_retention(self) -> dict[str, Any]:
        """Enforce retention policy."""
        return await self.retention.enforce()

    async def rebuild_index(self) -> int:
        """Rebuild the search index."""
        return await self.indexer.rebuild()
