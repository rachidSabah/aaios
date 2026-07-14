"""Memory ranking — cross-encoder rerank + graph topology boost.

The ranking module takes the raw results from vector search, graph
traversal, and keyword search, and produces a unified ranked list.

Scoring (configurable weights):
  - Vector similarity score (0.0 - 1.0)
  - Graph topology boost (items connected to high-relevance nodes get +0.2)
  - Keyword match score (0.0 - 1.0)
  - Recency boost (recent items get a small boost)

The final score is a weighted sum, clamped to [0.0, 1.0].
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from core.contracts.memory.item import MemoryItem
from core.contracts.memory.query import RankedItem
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["MemoryRanker", "RankConfig"]


class RankConfig:
    """Configuration for the memory ranker."""

    def __init__(
        self,
        *,
        vector_weight: float = 0.5,
        graph_boost: float = 0.2,
        keyword_weight: float = 0.2,
        recency_weight: float = 0.1,
        recency_halflife_days: float = 30.0,
    ) -> None:
        self.vector_weight = vector_weight
        self.graph_boost = graph_boost
        self.keyword_weight = keyword_weight
        self.recency_weight = recency_weight
        self.recency_halflife_days = recency_halflife_days


class MemoryRanker:
    """Ranks memory items by combining multiple signals.

    Phase 7: uses a simple weighted-sum scoring (no cross-encoder model —
    that requires a separate ML model and is deferred to Phase 8+ with the
    Security Layer). The current implementation uses:
      - Vector cosine similarity (from the vector store)
      - Graph topology boost (from the knowledge graph)
      - Keyword overlap (simple TF-IDF-like score)
      - Recency (exponential decay)
    """

    def __init__(self, config: RankConfig | None = None) -> None:
        self._config = config or RankConfig()

    def rank(
        self,
        items: list[MemoryItem],
        query_text: str,
        *,
        vector_scores: dict[UUID, float] | None = None,
        graph_neighbor_ids: dict[UUID, list[UUID]] | None = None,
        keyword_scores: dict[UUID, float] | None = None,
    ) -> list[RankedItem]:
        """Rank items by combined score.

        Args:
            items: the items to rank.
            query_text: the query text (for keyword matching).
            vector_scores: pre-computed vector similarity scores (item_id → score).
            graph_neighbor_ids: graph neighbors for each item (for topology boost).
            keyword_scores: pre-computed keyword match scores.

        Returns:
            Ranked items, sorted by score descending.
        """
        vector_scores = vector_scores or {}
        graph_neighbor_ids = graph_neighbor_ids or {}
        keyword_scores = keyword_scores or {}

        query_terms = set(query_text.lower().split())
        now = datetime.now(UTC)

        results: list[RankedItem] = []
        for item in items:
            breakdown: dict[str, float] = {}

            # Vector score
            vec_score = vector_scores.get(item.id, 0.0)
            breakdown["vector"] = vec_score

            # Graph boost: if this item has graph neighbors that are also in the
            # result set, boost its score
            neighbors = graph_neighbor_ids.get(item.id, [])
            graph_score = min(1.0, len(neighbors) * 0.1) if neighbors else 0.0
            breakdown["graph"] = graph_score

            # Keyword score (if not pre-computed, compute from content)
            kw_score = keyword_scores.get(item.id, -1.0)
            if kw_score < 0:
                kw_score = self._keyword_score(item.content, query_terms)
            breakdown["keyword"] = kw_score

            # Recency score
            age = (now - item.created_at).total_seconds()
            halflife_s = self._config.recency_halflife_days * 86400
            recency_score = math.exp(-age / halflife_s) if age > 0 else 1.0
            breakdown["recency"] = recency_score

            # Weighted sum
            total = (
                vec_score * self._config.vector_weight
                + graph_score * self._config.graph_boost
                + kw_score * self._config.keyword_weight
                + recency_score * self._config.recency_weight
            )
            total = min(1.0, max(0.0, total))

            source = "hybrid"
            if vec_score > 0 and graph_score == 0 and kw_score == 0:
                source = "vector"
            elif vec_score == 0 and graph_score > 0:
                source = "graph"
            elif vec_score == 0 and kw_score > 0:
                source = "keyword"

            results.append(
                RankedItem(
                    item=item,
                    score=total,
                    score_breakdown=breakdown,
                    source=source,
                    graph_neighbors=neighbors,
                )
            )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    @staticmethod
    def _keyword_score(content: str, query_terms: set[str]) -> float:
        """Compute a simple keyword overlap score."""
        if not query_terms:
            return 0.0
        content_terms = set(content.lower().split())
        if not content_terms:
            return 0.0
        overlap = len(query_terms & content_terms)
        return overlap / len(query_terms)
