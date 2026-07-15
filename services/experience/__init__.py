"""AAiOS Experience & Learning Engine — v2.1.

A modular subsystem that learns from every execution. Captures full
lifecycle records (ExperienceRecord), indexes them for semantic search,
mines patterns, computes reliability scores, and feeds the adaptive
router.

Components:
  - models: immutable ExperienceRecord + supporting types
  - store: persistent JSON storage with in-memory indices
  - collector: event-bus subscriber that builds records from live events
  - retriever: TF-IDF semantic search + pre-defined search types
  - analyzer: pattern discovery (successes, failures, fixes)
  - scorer: reliability scores for agents, providers, capabilities
  - replayer: replay past executions (dry_run / re_execute / compare)
  - lifecycle: exporter (JSON/CSV), compressor, retention manager
  - engine: top-level facade

Integration points (all backward-compatible):
  - Subscribes to the existing event bus (no changes needed)
  - Adds 9 new API endpoints to surfaces/api/app.py
  - Adds 7 new CLI commands to surfaces/cli/__main__.py
  - Adds 2 new dashboard pages (/experience, /learning)
"""

from __future__ import annotations

from services.experience.analyzer import (
    AgentReliability,
    CapabilityReliability,
    ExperienceAnalyzer,
    ExperienceScorer,
    FailurePattern,
    LearningStats,
    PatternReport,
    ProviderReliability,
    SuccessPattern,
)
from services.experience.collector import ExperienceCollector, InFlightExecution
from services.experience.engine import LearningEngine
from services.experience.lifecycle import (
    CompressedExperience,
    ExperienceCompressor,
    ExperienceExporter,
    ExperienceRetentionManager,
    RetentionPolicy,
)
from services.experience.models import (
    ArtifactRef,
    ExecutionStep,
    ExperienceOutcome,
    ExperienceRecord,
    KnowledgeRef,
    ResourceUsage,
    TokenUsage,
    UserFeedback,
)
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

__all__ = [
    "AgentReliability",
    "ArtifactRef",
    "CapabilityReliability",
    "CompressedExperience",
    "ExecutionStep",
    "ExperienceAnalyzer",
    "ExperienceCollector",
    "ExperienceCompressor",
    "ExperienceExporter",
    "ExperienceFilter",
    "ExperienceIndexer",
    "ExperienceNotFoundError",
    "ExperienceOutcome",
    "ExperienceRecord",
    "ExperienceReplayer",
    "ExperienceRetentionManager",
    "ExperienceRetriever",
    "ExperienceScorer",
    "ExperienceStore",
    "ExperienceSummary",
    "InFlightExecution",
    "KnowledgeRef",
    "LearningEngine",
    "LearningStats",
    "PatternReport",
    "ReplayMode",
    "ReplayResult",
    "ResourceUsage",
    "RetentionPolicy",
    "SearchResult",
    "SearchType",
    "SuccessPattern",
    "FailurePattern",
    "TokenUsage",
    "UserFeedback",
    "ProviderReliability",
]
