"""AAiOS v5.2 — Autonomous Software Engineering Platform.

An Engineering Intelligence Layer with planning, metrics, architecture
analysis, impact analysis, recommendations, risk assessment, reviews,
test intelligence, documentation intelligence, repository evolution,
release readiness, developer productivity, and a repository health center.

Modules:
  - models: RepositoryInfo, RepositoryAnalysis, FileAnalysis, CodeMetric, etc.
  - repository_engine: RepositoryIntelligenceEngine, CodeIntelligenceEngine,
    ArchitectureIntelligenceEngine
  - agents: EngineeringAgentOrganization (16 agents), CapabilityRegistry,
    EngineeringWorkspaceManager
  - intelligence: PlanningEngine, MetricsEngine, ArchitectureAnalysisEngine,
    ImpactAnalysisEngine, RecommendationEngine, RiskEngine
  - review_engine: EngineeringReviewEngine (12 review types) [Phase 17]
  - test_intelligence: TestIntelligenceEngine [Phase 18]
  - documentation_intelligence: DocumentationIntelligenceEngine [Phase 19]
  - evolution_engine: RepositoryEvolutionEngine [Phase 20]
  - release_readiness: ReleaseReadinessEngine [Phase 21]
  - productivity_engine: DeveloperProductivityEngine [Phase 22]
  - health_center: RepositoryHealthCenter [Phase 23]
  - manager: EngineeringManager facade

Integration (backward-compatible):
  - Sits above Knowledge Platform (v5.1) and Cognitive Layer (v5.0)
  - Read-only — never modifies production code
  - All recommendations require human approval
"""

from __future__ import annotations

from services.engineering.agents import (
    CapabilityRegistry,
    EngineeringAgentOrganization,
    EngineeringWorkspaceManager,
)
from services.engineering.documentation_intelligence import (
    DocAnalysisReport,
    DocIssue,
    DocPageInfo,
    DocType,
    DocumentationIntelligenceEngine,
)
from services.engineering.evolution_engine import (
    CommitInfo,
    EvolutionDashboard,
    EvolutionReport,
    ReleaseInfo,
    RepositoryEvolutionEngine,
    TimelineEntry,
)
from services.engineering.health_center import (
    HealthDimension,
    HealthDimensionResult,
    HealthReport,
    HealthTrend,
    RepositoryHealthCenter,
)
from services.engineering.intelligence import (
    ArchAnalysisResult,
    EngineeringMetrics,
    EngPlan,
    EngPlanItem,
    EngRecommendation,
    EngRiskAssessment,
    ImpactResult,
    MetricsEngine,
    PlanningEngine,
    RiskEngine,
)
from services.engineering.manager import EngineeringManager
from services.engineering.models import (
    ArchRecommendation,
    CodeMetric,
    EngCapability,
    EngineeringAgentManifest,
    EngWorkspace,
    EngWorkspaceSession,
    FileAnalysis,
    LanguageType,
    RepoGraphEdge,
    RepoGraphNode,
    RepositoryAnalysis,
    RepositoryGraph,
    RepositoryInfo,
    RepositoryIssue,
)
from services.engineering.productivity_engine import (
    DeveloperProductivityEngine,
    DORAMetrics,
    ProductivityDashboard,
    ProductivityMetrics,
    ProductivityReport,
    ProductivityTrend,
)
from services.engineering.release_readiness import (
    CertificationReport,
    ReadinessDimension,
    ReadinessDimensionResult,
    ReleaseReadinessEngine,
    ReleaseReadinessReport,
)
from services.engineering.repository_engine import (
    ArchitectureIntelligenceEngine,
    CodeIntelligenceEngine,
    RepositoryIntelligenceEngine,
)
from services.engineering.review_engine import (
    EngineeringReviewEngine,
    ReviewFinding,
    ReviewReport,
    ReviewType,
)
from services.engineering.test_intelligence import (
    TestCaseInfo,
    TestCoverageReport,
    TestIntelligenceEngine,
    TestRiskReport,
    TestSuiteAnalysis,
    TestType,
)

__all__ = [
    "ArchAnalysisResult",
    "ArchRecommendation",
    "ArchitectureIntelligenceEngine",
    "CapabilityRegistry",
    "CertificationReport",
    "CodeIntelligenceEngine",
    "CodeMetric",
    "CommitInfo",
    "DORAMetrics",
    "DocAnalysisReport",
    "DocIssue",
    "DocPageInfo",
    "DocType",
    "DocumentationIntelligenceEngine",
    "DeveloperProductivityEngine",
    "EngCapability",
    "EngPlan",
    "EngPlanItem",
    "EngRecommendation",
    "EngRiskAssessment",
    "EngWorkspace",
    "EngWorkspaceSession",
    "EngineeringAgentManifest",
    "EngineeringAgentOrganization",
    "EngineeringManager",
    "EngineeringMetrics",
    "EngineeringReviewEngine",
    "EngineeringWorkspaceManager",
    "EvolutionDashboard",
    "EvolutionReport",
    "FileAnalysis",
    "HealthDimension",
    "HealthDimensionResult",
    "HealthReport",
    "HealthTrend",
    "ImpactResult",
    "LanguageType",
    "MetricsEngine",
    "PlanningEngine",
    "ProductivityDashboard",
    "ProductivityMetrics",
    "ProductivityReport",
    "ProductivityTrend",
    "ReadinessDimension",
    "ReadinessDimensionResult",
    "ReleaseInfo",
    "ReleaseReadinessEngine",
    "ReleaseReadinessReport",
    "RepoGraphEdge",
    "RepoGraphNode",
    "RepositoryAnalysis",
    "RepositoryEvolutionEngine",
    "RepositoryGraph",
    "RepositoryHealthCenter",
    "RepositoryInfo",
    "RepositoryIntelligenceEngine",
    "RepositoryIssue",
    "ReviewFinding",
    "ReviewReport",
    "ReviewType",
    "RiskEngine",
    "TestCaseInfo",
    "TestCoverageReport",
    "TestIntelligenceEngine",
    "TestRiskReport",
    "TestSuiteAnalysis",
    "TestType",
    "TimelineEntry",
]
