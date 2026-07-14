"""Memory query contracts — for recall and ranking."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.memory.item import MemoryItem, MemoryScope

__all__ = ["MemoryQuery", "MemoryQueryResult", "RankedItem"]


class MemoryQuery(BaseModel):
    """A query to the memory system.

    Can filter by scope, metadata, time range, and content.
    Can request vector similarity search, graph traversal, or both (hybrid).
    """

    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(description="The natural-language query.")
    scope: MemoryScope | None = Field(default=None, description="If set, only search this scope.")
    k: int = Field(default=10, ge=1, description="Max results to return.")
    # Filters
    metadata_filter: dict[str, Any] = Field(default_factory=dict)
    created_after: datetime | None = None
    created_before: datetime | None = None
    # Search mode
    use_vector: bool = Field(default=True, description="Use vector similarity search.")
    use_graph: bool = Field(default=True, description="Use knowledge graph traversal.")
    use_keyword: bool = Field(default=True, description="Use keyword/FTS search.")
    # Ranking
    rerank: bool = Field(default=True, description="Apply cross-encoder reranking.")
    graph_boost: bool = Field(
        default=True, description="Boost items connected to high-relevance nodes."
    )
    # Context window budget
    max_tokens: int | None = Field(
        default=None, description="If set, truncate results to fit this token budget."
    )

    def to_reranked(self, items: list[MemoryItem]) -> list[MemoryItem]:
        """Sort items by score descending."""
        return sorted(items, key=lambda i: i.score, reverse=True)


class RankedItem(BaseModel):
    """A memory item with ranking metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    item: MemoryItem
    score: float = Field(ge=0.0, le=1.0)
    score_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description='e.g. {"vector": 0.8, "graph": 0.6, "keyword": 0.3}',
    )
    source: str = Field(default="vector", description="vector, graph, keyword, hybrid")
    graph_neighbors: list[UUID] = Field(
        default_factory=list,
        description="If from graph traversal, the neighbor node IDs.",
    )


class MemoryQueryResult(BaseModel):
    """The result of a memory query."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: MemoryQuery
    items: list[RankedItem] = Field(default_factory=list)
    total_found: int = Field(default=0, ge=0)
    truncated: bool = Field(
        default=False, description="True if results were truncated to fit token budget."
    )
    actual_tokens: int = Field(default=0, ge=0)
    elapsed_s: float = Field(default=0.0, ge=0.0)
