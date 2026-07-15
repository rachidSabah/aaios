"""AAiOS v5.1 — Enterprise Knowledge & Memory Platform.

A unified Enterprise Knowledge Operating System with:
  - 15 coordinated memory systems
  - Memory Orchestrator
  - Knowledge Repository
  - Hybrid Search Engine
  - Enterprise RAG
  - Knowledge Governance
  - Enterprise Knowledge Graph
  - Knowledge Intelligence Engine (understanding, gaps, conflicts, quality)
  - Autonomous Learning Engine (lessons, playbooks)
  - Repository Intelligence (dead code, missing docs, tests)
  - Document Intelligence (PDF, DOCX, MD, JSON, CSV, Python)
  - Quality Assurance (validation, repair suggestions)
  - Recommendation Engine (documents, lessons, playbooks, memories)

Integration (backward-compatible):
  - Sits above Cognitive Intelligence Layer (v5.0)
  - Extends existing Memory Manager (v1.0) with 15 typed memory systems
  - No changes to existing runtime — pure extension
"""

from __future__ import annotations

from services.knowledge.intelligence import (
    AutonomousLearningEngine,
    KnowledgeGap,
    KnowledgeInsight,
    KnowledgeIntelligenceEngine,
    KnowledgeQualityReport,
    Lesson,
    Playbook,
    RecommendationEngine,
)
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
from services.knowledge.repo_intelligence import (
    DocIntelligenceResult,
    DocumentIntelligence,
    QualityAssurance,
    QualityIssue,
    RepoAnalysis,
    RepoIssue,
    RepositoryIntelligenceEngine,
)

__all__ = [
    "AccessLevel",
    "AutonomousLearningEngine",
    "ConflictReport",
    "DocIntelligenceResult",
    "DocumentIntelligence",
    "EnterpriseKnowledgeGraph",
    "HybridSearchEngine",
    "KnowledgeCollection",
    "KnowledgeEntry",
    "KnowledgeEntryStatus",
    "KnowledgeGap",
    "KnowledgeGovernance",
    "KnowledgeInsight",
    "KnowledgeIntelligenceEngine",
    "KnowledgePermission",
    "KnowledgePlatform",
    "KnowledgeQualityReport",
    "KnowledgeSearchResult",
    "KnowledgeVersion",
    "KnowledgeWorkspace",
    "Lesson",
    "MemoryOrchestrator",
    "MemoryRecord",
    "MemoryScope",
    "MemoryStore",
    "MemoryType",
    "Playbook",
    "QualityAssurance",
    "QualityIssue",
    "RAGResult",
    "RecommendationEngine",
    "RepoAnalysis",
    "RepoIssue",
    "RepositoryIntelligenceEngine",
    "RetrievalEngine",
    "RetrievalRequest",
    "StoragePolicy",
]
