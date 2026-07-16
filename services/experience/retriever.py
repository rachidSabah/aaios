"""Experience Indexer + Retriever — semantic search over experiences.

The indexer builds a keyword index from each experience's goal, input_summary,
output_summary, capabilities, and failure_reason. The retriever uses TF-IDF
scoring to find the most similar experiences to a query.

This is a lightweight implementation (no external ML). It mirrors the
memory subsystem's hash-based embedding approach — fast, deterministic,
and dependency-free. For production semantic search, swap the scoring
function with a real embedding model.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from services.experience.models import ExperienceRecord
from services.experience.store import ExperienceStore

_log = get_logger(__name__)

__all__ = [
    "ExperienceIndexer",
    "ExperienceRetriever",
    "SearchResult",
    "SearchType",
]


class SearchType:
    """Pre-defined search types."""

    SIMILAR_SUCCESSES = "similar_successes"
    SIMILAR_FAILURES = "similar_failures"
    BEST_AGENT_FOR_CAPABILITY = "best_agent_for_capability"
    FASTEST_PROVIDER = "fastest_provider"
    CHEAPEST_PROVIDER = "cheapest_provider"
    HIGHEST_QUALITY = "highest_quality"
    SIMILAR_WORKFLOWS = "similar_workflows"


# Stop words to exclude from indexing
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "shall",
    "can", "need", "ought", "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "this", "that", "these", "those", "of", "in", "on", "at",
    "to", "for", "with", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "up", "down", "out", "off",
    "over", "under", "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "no", "not", "only", "own",
    "same", "so", "than", "too", "very", "s", "t", "if", "because",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, excluding stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


@dataclass
class SearchResult:
    """A single search result."""

    experience: ExperienceRecord
    score: float
    matched_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": str(self.experience.experience_id),
            "score": round(self.score, 4),
            "matched_terms": list(self.matched_terms),
            "goal": self.experience.goal,
            "agent_id": self.experience.agent_id,
            "outcome": self.experience.outcome,
            "quality": round(self.experience.quality_score(), 4),
            "timestamp": self.experience.timestamp.isoformat(),
        }


class ExperienceIndexer:
    """Builds and maintains a TF-IDF index over experiences.

    The index is rebuilt on demand from the store. For large stores, you
    can rebuild periodically rather than on every query.
    """

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store
        self._lock = asyncio.Lock()
        self._index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        # term -> [(experience_id_str, term_frequency)]
        self._doc_lengths: dict[str, int] = {}
        self._total_docs: int = 0
        self._built = False

    async def rebuild(self) -> int:
        """Rebuild the index from all records in the store."""
        records = await self._store.all_records()
        async with self._lock:
            self._index.clear()
            self._doc_lengths.clear()
            self._total_docs = len(records)
            for record in records:
                doc_id = str(record.experience_id)
                # Combine all text fields
                text = " ".join([
                    record.goal,
                    record.input_summary,
                    record.output_summary,
                    " ".join(record.capabilities_used),
                    record.failure_reason or "",
                    record.agent_type,
                ])
                tokens = _tokenize(text)
                self._doc_lengths[doc_id] = len(tokens)
                tf = Counter(tokens)
                for term, count in tf.items():
                    self._index[term].append((doc_id, count))
            self._built = True
            _log.info("Experience index built: %d docs, %d unique terms", self._total_docs, len(self._index))
        return self._total_docs

    def _idf(self, term: str) -> float:
        """Inverse document frequency for a term."""
        df = len(self._index.get(term, []))
        if df == 0 or self._total_docs == 0:
            return 0.0
        return math.log(self._total_docs / df)

    def _tfidf(self, term: str, doc_id: str, term_freq: int) -> float:
        """TF-IDF score for a term in a document."""
        return term_freq * self._idf(term)

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Search experiences by text query. Returns ranked results."""
        if not self._built:
            await self.rebuild()
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        # Score each candidate document
        scores: dict[str, float] = defaultdict(float)
        matched_terms: dict[str, set[str]] = defaultdict(set)
        for term in query_tokens:
            for doc_id, tf in self._index.get(term, []):
                score = self._tfidf(term, doc_id, tf)
                scores[doc_id] += score
                matched_terms[doc_id].add(term)
        # Normalize by document length
        for doc_id in scores:
            length = self._doc_lengths.get(doc_id, 1)
            scores[doc_id] /= max(1, length)
        # Rank and return top N
        ranked = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]
        # Fetch full records
        from uuid import UUID
        results: list[SearchResult] = []
        for doc_id, score in ranked:
            if score < min_score:
                continue
            try:
                record = await self._store.get(UUID(doc_id))
                results.append(SearchResult(
                    experience=record,
                    score=score,
                    matched_terms=sorted(matched_terms[doc_id]),
                ))
            except Exception:
                pass
        return results


class ExperienceRetriever:
    """High-level retrieval interface with pre-defined search types.

    Wraps the indexer with convenience methods for common queries:
      - find similar successes/failures
      - find best agent for a capability
      - find fastest/cheapest provider
      - find highest-quality workflows
    """

    def __init__(self, store: ExperienceStore, indexer: ExperienceIndexer) -> None:
        self._store = store
        self._indexer = indexer

    async def similar(
        self,
        query: str,
        *,
        limit: int = 10,
        outcome: str | None = None,
    ) -> list[SearchResult]:
        """Find experiences similar to a text query."""
        results = await self._indexer.search(query, limit=limit * 2)
        if outcome is not None:
            results = [r for r in results if r.experience.outcome == outcome]
        return results[:limit]

    async def similar_successes(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Find successful experiences similar to a query."""
        from services.experience.models import ExperienceOutcome
        return await self.similar(query, limit=limit, outcome=ExperienceOutcome.SUCCESS.value)

    async def similar_failures(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Find failed experiences similar to a query (for debugging)."""
        from services.experience.models import ExperienceOutcome
        return await self.similar(query, limit=limit, outcome=ExperienceOutcome.FAILURE.value)

    async def best_agent_for_capability(
        self,
        capability: str,
        *,
        min_experiences: int = 3,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find the agent with the highest success rate for a capability."""
        from services.experience.store import ExperienceFilter
        records = await self._store.query(
            ExperienceFilter(capability=capability, success=True), limit=1000,
        )
        if not records:
            return []
        # Group by agent
        by_agent: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in records:
            by_agent[r.agent_id].append(r)
        # Score each agent
        scored: list[dict[str, Any]] = []
        for agent_id, agent_records in by_agent.items():
            if len(agent_records) < min_experiences:
                continue
            success_rate = sum(1 for r in agent_records if r.success) / len(agent_records)
            avg_quality = sum(r.quality_score() for r in agent_records) / len(agent_records)
            avg_latency = sum(r.latency_s for r in agent_records) / len(agent_records)
            avg_cost = sum(r.cost_usd for r in agent_records) / len(agent_records)
            scored.append({
                "agent_id": agent_id,
                "experience_count": len(agent_records),
                "success_rate": round(success_rate, 4),
                "avg_quality": round(avg_quality, 4),
                "avg_latency_s": round(avg_latency, 4),
                "avg_cost_usd": round(avg_cost, 6),
                "score": round(success_rate * 0.5 + avg_quality * 0.5, 4),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def fastest_provider(
        self,
        *,
        min_experiences: int = 3,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find providers with the lowest average latency."""
        records = await self._store.all_records()
        by_provider: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in records:
            if r.provider:
                by_provider[r.provider].append(r)
        scored: list[dict[str, Any]] = []
        for provider, provider_records in by_provider.items():
            if len(provider_records) < min_experiences:
                continue
            avg_latency = sum(r.latency_s for r in provider_records) / len(provider_records)
            scored.append({
                "provider": provider,
                "experience_count": len(provider_records),
                "avg_latency_s": round(avg_latency, 4),
                "avg_cost_usd": round(
                    sum(r.cost_usd for r in provider_records) / len(provider_records), 6,
                ),
            })
        scored.sort(key=lambda x: x["avg_latency_s"])
        return scored[:limit]

    async def cheapest_provider(
        self,
        *,
        min_experiences: int = 3,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find providers with the lowest average cost."""
        records = await self._store.all_records()
        by_provider: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in records:
            if r.provider:
                by_provider[r.provider].append(r)
        scored: list[dict[str, Any]] = []
        for provider, provider_records in by_provider.items():
            if len(provider_records) < min_experiences:
                continue
            avg_cost = sum(r.cost_usd for r in provider_records) / len(provider_records)
            scored.append({
                "provider": provider,
                "experience_count": len(provider_records),
                "avg_cost_usd": round(avg_cost, 6),
                "avg_latency_s": round(
                    sum(r.latency_s for r in provider_records) / len(provider_records), 4,
                ),
            })
        scored.sort(key=lambda x: x["avg_cost_usd"])
        return scored[:limit]

    async def highest_quality_workflows(
        self,
        *,
        min_experiences: int = 2,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find workflows with the highest average quality score."""
        records = await self._store.all_records()
        by_workflow: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for r in records:
            if r.workflow_id:
                by_workflow[r.workflow_id].append(r)
        scored: list[dict[str, Any]] = []
        for wf_id, wf_records in by_workflow.items():
            if len(wf_records) < min_experiences:
                continue
            avg_quality = sum(r.quality_score() for r in wf_records) / len(wf_records)
            success_rate = sum(1 for r in wf_records if r.success) / len(wf_records)
            scored.append({
                "workflow_id": wf_id,
                "experience_count": len(wf_records),
                "avg_quality": round(avg_quality, 4),
                "success_rate": round(success_rate, 4),
            })
        scored.sort(key=lambda x: x["avg_quality"], reverse=True)
        return scored[:limit]

    async def search(
        self,
        query: str,
        *,
        search_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Generic search interface — returns results based on search_type."""
        if search_type == SearchType.SIMILAR_SUCCESSES:
            search_results = await self.similar_successes(query, limit=limit)
            return {"type": search_type, "results": [r.to_dict() for r in search_results]}
        if search_type == SearchType.SIMILAR_FAILURES:
            search_results = await self.similar_failures(query, limit=limit)
            return {"type": search_type, "results": [r.to_dict() for r in search_results]}
        if search_type == SearchType.BEST_AGENT_FOR_CAPABILITY:
            agent_rankings = await self.best_agent_for_capability(query, limit=limit)
            return {"type": search_type, "results": agent_rankings}
        if search_type == SearchType.FASTEST_PROVIDER:
            provider_rankings = await self.fastest_provider(limit=limit)
            return {"type": search_type, "results": provider_rankings}
        if search_type == SearchType.CHEAPEST_PROVIDER:
            provider_rankings = await self.cheapest_provider(limit=limit)
            return {"type": search_type, "results": provider_rankings}
        if search_type == SearchType.HIGHEST_QUALITY:
            workflow_rankings = await self.highest_quality_workflows(limit=limit)
            return {"type": search_type, "results": workflow_rankings}
        # Default: semantic search
        search_results = await self.similar(query, limit=limit)
        return {"type": "semantic", "results": [r.to_dict() for r in search_results]}
