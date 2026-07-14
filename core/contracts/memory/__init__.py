"""Memory contracts — MemoryItem, MemoryScope, MemoryQuery, MemoryRankingResult.

These contracts are L1 (kernel) — used by the Memory Manager (L2), agents
(L3), and the Supervisor (L4). They define the universal memory format that
all memory adapters (vector, graph, relational) work with.
"""

from __future__ import annotations

from core.contracts.memory.graph import (
    GraphEdge,
    GraphNode,
    KnowledgeGraphProtocol,
)
from core.contracts.memory.item import (
    MemoryItem,
    MemoryScope,
    MemoryScopeType,
    MemoryVector,
)
from core.contracts.memory.query import MemoryQuery, MemoryQueryResult, RankedItem

__all__ = [
    "GraphEdge",
    "GraphNode",
    "KnowledgeGraphProtocol",
    "MemoryItem",
    "MemoryQuery",
    "MemoryQueryResult",
    "MemoryScope",
    "MemoryScopeType",
    "MemoryVector",
    "RankedItem",
]
