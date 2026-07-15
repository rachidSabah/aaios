"""AAiOS v5.1 — Enterprise Knowledge & Memory Platform.

A unified Enterprise Knowledge Operating System with:
  - 15 coordinated memory systems (short-term, long-term, working, semantic,
    procedural, episodic, project, mission, workflow, agent, provider,
    user, organization, execution, conversation)
  - Memory Orchestrator (auto-promote/demote, merge, compress, context windows)
  - Knowledge Repository (entries, versions, collections, workspaces)
  - Hybrid Search Engine (keyword + semantic + fuzzy + graph)
  - Enterprise RAG (citation, conflict detection, freshness, dedup)
  - Knowledge Governance (RBAC, approval, publishing, legal hold, quality)
  - Enterprise Knowledge Graph (20+ node types, traversal, impact analysis)

Integration (backward-compatible):
  - Sits above Cognitive Intelligence Layer (v5.0)
  - Extends existing Memory Manager (v1.0) with 15 typed memory systems
  - No changes to existing runtime — pure extension
"""

from __future__ import annotations

from services.knowledge.memory_platform import MemoryOrchestrator, MemoryStore
from services.knowledge.models import (
    AccessLevel,
    ConflictReport,
    KnowledgeCollection,
    KnowledgeEntry,
    KnowledgeEntryStatus,
    KnowledgePermission,
    KnowledgeSearchResult,
    KnowledgeVersion,
    KnowledgeWorkspace,
    MemoryRecord,
    MemoryScope,
    MemoryType,
    RAGResult,
    RetrievalRequest,
    StoragePolicy,
)
from services.knowledge.platform import (
    EnterpriseKnowledgeGraph,
    HybridSearchEngine,
    KnowledgeGovernance,
    KnowledgePlatform,
    RetrievalEngine,
)

__all__ = [
    "AccessLevel",
    "ConflictReport",
    "EnterpriseKnowledgeGraph",
    "HybridSearchEngine",
    "KnowledgeCollection",
    "KnowledgeEntry",
    "KnowledgeEntryStatus",
    "KnowledgeGovernance",
    "KnowledgePermission",
    "KnowledgePlatform",
    "KnowledgeSearchResult",
    "KnowledgeVersion",
    "KnowledgeWorkspace",
    "MemoryOrchestrator",
    "MemoryRecord",
    "MemoryScope",
    "MemoryStore",
    "MemoryType",
    "RAGResult",
    "RetrievalEngine",
    "RetrievalRequest",
    "StoragePolicy",
]
