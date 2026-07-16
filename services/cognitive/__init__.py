"""AAiOS v5.0 — Enterprise Cognitive Intelligence Platform.

A cognitive intelligence layer that makes AAiOS self-aware, self-learning,
self-predicting, and self-optimizing — while never modifying production
code automatically.

Modules:
  1. Enterprise Experience Engine — persist every execution with cognitive fields
  2. Learning Engine — explainable statistical learning from history
  3. Prediction Engine — pre-execution predictions with explanations
  4. Optimization Engine — recommendations (never auto-applied)
  5. Enterprise Knowledge Graph — nodes, relationships, traversal, impact analysis
  6. Digital Twin — real-time system model (extends existing intelligence module)
  7. Architecture Intelligence — dead code, drift, bottlenecks detection
  8. Repository Intelligence — doc gaps, SBOM, dependency reports
  9. Executive Dashboard — 9 new pages
  10. Enterprise Reporting — 11 report types, multi-format export
  11. Enterprise API — 10 new endpoint groups
  12. CLI — 10 new command groups

Integration (backward-compatible):
  - Sits above the existing Intelligence Engine (v3.1)
  - Wraps the existing Experience Engine (v2.1)
  - Read-only — never modifies production code
  - All recommendations require Supervisor approval
"""

from __future__ import annotations

from services.cognitive.engines import (
    ArchitectureIntelligence,
    CognitiveOptimizationEngine,
    CognitivePredictionEngine,
    EnterpriseKnowledgeGraph,
    EnterpriseReporting,
    RepositoryIntelligence,
)
from services.cognitive.experience_engine import CognitiveExperience, CognitiveExperienceEngine
from services.cognitive.learning_engine import CognitiveLearningEngine
from services.cognitive.manager import CognitiveManager
from services.cognitive.models import (
    ArchIssue,
    ArchIssueType,
    EnterpriseReport,
    EnterpriseReportType,
    GraphEdge,
    GraphNode,
    GraphType,
    KnowledgeGraph,
    LearningInsight,
    LearningMetric,
    PredictionResult,
    PredictionType,
    Recommendation,
    RecommendationStatus,
    RecommendationType,
)

__all__ = [
    "ArchIssue",
    "ArchIssueType",
    "ArchitectureIntelligence",
    "CognitiveExperience",
    "CognitiveExperienceEngine",
    "CognitiveLearningEngine",
    "CognitiveManager",
    "CognitiveOptimizationEngine",
    "CognitivePredictionEngine",
    "EnterpriseKnowledgeGraph",
    "EnterpriseReport",
    "EnterpriseReportType",
    "EnterpriseReporting",
    "GraphEdge",
    "GraphNode",
    "GraphType",
    "KnowledgeGraph",
    "LearningInsight",
    "LearningMetric",
    "PredictionResult",
    "PredictionType",
    "Recommendation",
    "RecommendationStatus",
    "RecommendationType",
    "RepositoryIntelligence",
]
