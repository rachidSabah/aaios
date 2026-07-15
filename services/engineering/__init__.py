"""AAiOS v5.2 — Autonomous Software Engineering Platform.

An Engineering Intelligence Layer that makes AAiOS capable of understanding,
planning, reviewing, improving, documenting, and maintaining software
projects while remaining under explicit human supervision.

Modules:
  - models: RepositoryInfo, RepositoryAnalysis, RepositoryGraph, FileAnalysis,
    CodeMetric, ArchRecommendation, EngCapability, EngineeringAgentManifest,
    EngWorkspace, EngWorkspaceSession
  - repository_engine: RepositoryIntelligenceEngine (discovery + analysis),
    CodeIntelligenceEngine (AST analysis, 20 languages, complexity metrics),
    ArchitectureIntelligenceEngine (layer violations, circular deps, recommendations)
  - agents: EngineeringAgentOrganization (16 specialized agents),
    CapabilityRegistry, EngineeringWorkspaceManager
  - manager: EngineeringManager facade

Integration (backward-compatible):
  - Sits above Knowledge Platform (v5.1) and Cognitive Layer (v5.0)
  - Read-only — never modifies production code
  - All recommendations require human approval
  - Every recommendation includes confidence, risk, impact, affected files,
    reasoning, evidence, estimated effort, and rollback strategy
"""

from __future__ import annotations

from services.engineering.agents import (
    CapabilityRegistry,
    EngineeringAgentOrganization,
    EngineeringWorkspaceManager,
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
from services.engineering.repository_engine import (
    ArchitectureIntelligenceEngine,
    CodeIntelligenceEngine,
    RepositoryIntelligenceEngine,
)

__all__ = [
    "ArchRecommendation",
    "ArchitectureIntelligenceEngine",
    "CapabilityRegistry",
    "CodeIntelligenceEngine",
    "CodeMetric",
    "EngCapability",
    "EngWorkspace",
    "EngWorkspaceSession",
    "EngineeringAgentManifest",
    "EngineeringAgentOrganization",
    "EngineeringManager",
    "EngineeringWorkspaceManager",
    "FileAnalysis",
    "LanguageType",
    "RepoGraphEdge",
    "RepoGraphNode",
    "RepositoryAnalysis",
    "RepositoryGraph",
    "RepositoryInfo",
    "RepositoryIntelligenceEngine",
    "RepositoryIssue",
]
