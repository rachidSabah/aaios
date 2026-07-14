"""RAG pipeline — hybrid vector + graph + rerank + context-window budgeting.

The RAG pipeline orchestrates:
  1. Vector similarity search (via the Vector Store)
  2. Graph traversal (via the Knowledge Graph)
  3. Keyword search (simple TF-IDF)
  4. Reranking (via the Memory Ranker)
  5. Context window budgeting (via the Context Window Manager)

It returns a MemoryQueryResult with the final ranked items, truncated to
fit the token budget.
"""

from __future__ import annotations

import time
from uuid import UUID

from core.contracts.memory.item import MemoryItem
from core.contracts.memory.query import MemoryQuery, MemoryQueryResult, RankedItem
from core.logging import get_logger
from services.memory.context_window import ContextWindowManager, _estimate_tokens
from services.memory.knowledge_graph import InMemoryKnowledgeGraph
from services.memory.ranking import MemoryRanker
from services.memory.vector_store import InMemoryVectorStore

_log = get_logger(__name__)

__all__ = ["RAGPipeline"]


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline.

    Combines vector search, graph traversal, keyword matching, and reranking
    into a unified retrieval system.
    """

    def __init__(
        self,
        *,
        vector_store: InMemoryVectorStore | None = None,
        knowledge_graph: InMemoryKnowledgeGraph | None = None,
        ranker: MemoryRanker | None = None,
        context_window_manager: ContextWindowManager | None = None,
    ) -> None:
        self._vector_store = vector_store or InMemoryVectorStore()
        self._knowledge_graph = knowledge_graph or InMemoryKnowledgeGraph()
        self._ranker = ranker or MemoryRanker()
        self._context_window_manager = context_window_manager or ContextWindowManager()

    @property
    def vector_store(self) -> InMemoryVectorStore:
        """Return the vector store."""
        return self._vector_store

    @property
    def knowledge_graph(self) -> InMemoryKnowledgeGraph:
        """Return the knowledge graph."""
        return self._knowledge_graph

    async def retrieve(
        self,
        query: MemoryQuery,
        query_vector: list[float] | None = None,
    ) -> MemoryQueryResult:
        """Retrieve and rank items for a query.

        Args:
            query: the memory query.
            query_vector: pre-computed embedding of the query text. If None,
                only keyword + graph search is used (no vector search).

        Returns:
            The ranked results, truncated to fit the token budget.
        """
        start = time.monotonic()
        all_items: dict[UUID, MemoryItem] = {}
        vector_scores: dict[UUID, float] = {}
        graph_neighbor_ids: dict[UUID, list[UUID]] = {}
        keyword_scores: dict[UUID, float] = {}

        # 1. Vector search
        if query.use_vector and query_vector is not None:
            collection = str(query.scope) if query.scope else "all"
            results = await self._vector_store.search(
                collection=collection,
                query_vector=query_vector,
                k=query.k * 2,  # over-fetch for reranking
                filter=query.metadata_filter or None,
            )
            for item, score in results:
                all_items[item.id] = item
                vector_scores[item.id] = score

        # 2. Graph traversal
        if query.use_graph:
            # Find graph nodes matching the query text
            nodes = await self._knowledge_graph.find_nodes(name=query.query_text)
            for node in nodes:
                if node.memory_item_id is not None:
                    # Get the neighbors of this node
                    neighbors = await self._knowledge_graph.neighbors(node.id, max_depth=2)
                    neighbor_ids = [n.id for n, _ in neighbors]
                    graph_neighbor_ids[node.memory_item_id] = neighbor_ids
                    # The node itself might correspond to a memory item
                    # (we'd need to fetch it from the vector store — for now
                    # we just boost items that have graph neighbors)

        # 3. Keyword search (simple — scan all items in the scope)
        if query.use_keyword:
            query_terms = set(query.query_text.lower().split())
            for item in all_items.values():
                content_terms = set(item.content.lower().split())
                overlap = len(query_terms & content_terms)
                if overlap > 0:
                    keyword_scores[item.id] = overlap / len(query_terms)

        # 4. Rank
        items_list = list(all_items.values())
        ranked = self._ranker.rank(
            items_list,
            query.query_text,
            vector_scores=vector_scores,
            graph_neighbor_ids=graph_neighbor_ids,
            keyword_scores=keyword_scores,
        )

        # 5. Truncate to k
        ranked = ranked[: query.k]

        # 6. Context window budgeting
        actual_tokens = 0
        truncated = False
        if query.max_tokens is not None:
            final_ranked: list[RankedItem] = []
            for r in ranked:
                item_tokens = _estimate_tokens(r.item.content)
                if actual_tokens + item_tokens > query.max_tokens:
                    truncated = True
                    break
                final_ranked.append(r)
                actual_tokens += item_tokens
            ranked = final_ranked
        else:
            actual_tokens = sum(_estimate_tokens(r.item.content) for r in ranked)

        elapsed = time.monotonic() - start
        return MemoryQueryResult(
            query=query,
            items=ranked,
            total_found=len(all_items),
            truncated=truncated,
            actual_tokens=actual_tokens,
            elapsed_s=elapsed,
        )
