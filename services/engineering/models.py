"""Engineering Intelligence models — repository analysis, code metrics, architecture issues.

All models are immutable dataclasses with to_dict() for JSON serialization.
Every recommendation includes confidence, risk, impact, affected files, reasoning,
supporting evidence, estimated effort, and rollback strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "ArchRecommendation",
    "CodeMetric",
    "EngCapability",
    "EngWorkspace",
    "EngWorkspaceSession",
    "EngineeringAgentManifest",
    "FileAnalysis",
    "LanguageType",
    "RepoGraphNode",
    "RepoGraphEdge",
    "RepositoryAnalysis",
    "RepositoryGraph",
    "RepositoryInfo",
    "RepositoryIssue",
]


class LanguageType(StrEnum):
    """Supported programming languages for code intelligence."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    PHP = "php"
    RUBY = "ruby"
    SHELL = "shell"
    POWERSHELL = "powershell"
    YAML = "yaml"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    CSS = "css"
    SQL = "sql"


@dataclass
class RepositoryInfo:
    """Information about a discovered repository."""

    repo_id: str = field(default_factory=lambda: uuid4().hex[:12])
    path: str = ""
    name: str = ""
    repo_type: str = "monorepo"  # monorepo, polyrepo, nested, submodule
    branch: str = "main"
    is_main: bool = True
    file_count: int = 0
    line_count: int = 0
    language_breakdown: dict[str, int] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "path": self.path,
            "name": self.name,
            "repo_type": self.repo_type,
            "branch": self.branch,
            "is_main": self.is_main,
            "file_count": self.file_count,
            "line_count": self.line_count,
            "language_breakdown": dict(self.language_breakdown),
            "discovered_at": self.discovered_at.isoformat(),
        }


@dataclass
class RepositoryIssue:
    """An issue found in a repository."""

    issue_id: str = field(default_factory=lambda: uuid4().hex[:12])
    issue_type: str = ""  # dead_code, missing_doc, missing_test, circular_dep, arch_violation, etc.
    severity: str = "medium"
    file: str = ""
    line: int = 0
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "description": self.description,
            "recommendation": self.recommendation,
        }


@dataclass
class RepositoryAnalysis:
    """Complete repository analysis result."""

    repos: list[RepositoryInfo] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_tests: int = 0
    issues: list[RepositoryIssue] = field(default_factory=list)
    health_score: float = 0.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos": [r.to_dict() for r in self.repos],
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_classes": self.total_classes,
            "total_functions": self.total_functions,
            "total_tests": self.total_tests,
            "issues": [i.to_dict() for i in self.issues],
            "health_score": round(self.health_score, 2),
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class RepoGraphNode:
    """A node in the repository knowledge graph."""

    node_id: str = field(default_factory=lambda: uuid4().hex[:12])
    node_type: str = (
        ""  # repository, directory, package, module, class, function, test, config, etc.
    )
    name: str = ""
    path: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "path": self.path,
            "properties": dict(self.properties),
        }


@dataclass
class RepoGraphEdge:
    """An edge in the repository knowledge graph."""

    source_id: str = ""
    target_id: str = ""
    relationship: str = ""  # contains, imports, calls, depends_on, tests, inherits, implements
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
            "properties": dict(self.properties),
        }


@dataclass
class RepositoryGraph:
    """Repository knowledge graph snapshot."""

    nodes: list[RepoGraphNode] = field(default_factory=list)
    edges: list[RepoGraphEdge] = field(default_factory=list)
    built_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "built_at": self.built_at.isoformat(),
        }


@dataclass
class FileAnalysis:
    """Analysis of a single source file."""

    file_path: str = ""
    language: str = ""
    line_count: int = 0
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    complexity_score: float = 0.0
    maintainability_score: float = 0.0
    test_coverage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "line_count": self.line_count,
            "classes": list(self.classes),
            "functions": list(self.functions),
            "imports": list(self.imports),
            "complexity_score": round(self.complexity_score, 4),
            "maintainability_score": round(self.maintainability_score, 4),
            "test_coverage": round(self.test_coverage, 4),
        }


@dataclass
class CodeMetric:
    """Code quality metric."""

    name: str = ""
    value: float = 0.0
    unit: str = ""
    file: str = ""
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "unit": self.unit,
            "file": self.file,
            "explanation": self.explanation,
        }


@dataclass
class ArchRecommendation:
    """An architecture recommendation (never auto-applied).

    Every recommendation includes:
      - confidence, risk, impact
      - affected_files, reasoning
      - supporting_evidence
      - estimated_effort, rollback_strategy
    """

    recommendation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    recommendation_type: str = ""  # refactoring, abstraction, decoupling, etc.
    confidence: float = 0.5
    risk: str = "medium"  # low, medium, high
    impact: float = 0.5
    affected_files: list[str] = field(default_factory=list)
    reasoning: str = ""
    supporting_evidence: dict[str, Any] = field(default_factory=dict)
    estimated_effort_hours: float = 0.0
    rollback_strategy: str = ""
    requires_approval: bool = True
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "title": self.title,
            "description": self.description,
            "recommendation_type": self.recommendation_type,
            "confidence": round(self.confidence, 4),
            "risk": self.risk,
            "impact": round(self.impact, 4),
            "affected_files": list(self.affected_files),
            "reasoning": self.reasoning,
            "supporting_evidence": dict(self.supporting_evidence),
            "estimated_effort_hours": round(self.estimated_effort_hours, 2),
            "rollback_strategy": self.rollback_strategy,
            "requires_approval": self.requires_approval,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EngCapability:
    """Engineering capability for the capability registry."""

    capability_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    category: str = ""  # language, framework, database, cloud, testing, etc.
    proficiency: float = 0.5
    success_rate: float = 0.0
    avg_latency_s: float = 0.0
    avg_cost_usd: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "category": self.category,
            "proficiency": round(self.proficiency, 4),
            "success_rate": round(self.success_rate, 4),
            "avg_latency_s": round(self.avg_latency_s, 4),
            "avg_cost_usd": round(self.avg_cost_usd, 6),
            "sample_count": self.sample_count,
        }


@dataclass
class EngineeringAgentManifest:
    """Manifest for an engineering agent."""

    agent_id: str = ""
    agent_type: str = ""  # software_architect, backend_engineer, etc.
    display_name: str = ""
    capabilities: list[EngCapability] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "display_name": self.display_name,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "description": self.description,
        }


@dataclass
class EngWorkspaceSession:
    """An engineering workspace session."""

    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    repo_path: str = ""
    branch: str = "main"
    mission_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    navigation_history: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "repo_path": self.repo_path,
            "branch": self.branch,
            "mission_id": self.mission_id,
            "context": dict(self.context),
            "navigation_history": list(self.navigation_history),
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
        }


@dataclass
class EngWorkspace:
    """An engineering workspace."""

    workspace_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    repo_paths: list[str] = field(default_factory=list)
    sessions: list[EngWorkspaceSession] = field(default_factory=list)
    engineering_context: dict[str, Any] = field(default_factory=dict)
    knowledge_refs: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "repo_paths": list(self.repo_paths),
            "sessions": [s.to_dict() for s in self.sessions],
            "engineering_context": dict(self.engineering_context),
            "knowledge_refs": list(self.knowledge_refs),
            "created_at": self.created_at.isoformat(),
        }
