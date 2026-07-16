"""Phase 23 — Repository Health Center.

Monitors 8 dimensions of repository health: repository, architecture,
dependency, documentation, security, testing, release, knowledge.
Generates an overall health score, historical charts, trend analysis,
and improvement recommendations.

READ-ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "HealthDimension",
    "HealthDimensionResult",
    "HealthReport",
    "RepositoryHealthCenter",
    "HealthTrend",
]


class HealthDimension(StrEnum):
    """The eight repository health dimensions."""

    REPOSITORY = "repository"
    ARCHITECTURE = "architecture"
    DEPENDENCY = "dependency"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    TESTING = "testing"
    RELEASE = "release"
    KNOWLEDGE = "knowledge"


@dataclass
class HealthDimensionResult:
    """Health snapshot for a single dimension."""

    dimension: str = ""
    score: float = 0.0  # 0..100
    status: str = "warning"  # healthy | warning | critical
    summary: str = ""
    indicators: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    confidence: float = 0.6

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": round(self.score, 2),
            "status": self.status,
            "summary": self.summary,
            "indicators": dict(self.indicators),
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class HealthTrend:
    """A single point in a health trend."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    overall_score: float = 0.0
    by_dimension: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_score": round(self.overall_score, 2),
            "by_dimension": dict(self.by_dimension),
        }


@dataclass
class HealthReport:
    """A complete repository health report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    repository: str = ""
    overall_score: float = 0.0
    status: str = "warning"  # healthy | warning | critical
    dimensions: list[HealthDimensionResult] = field(default_factory=list)
    trend: list[HealthTrend] = field(default_factory=list)
    improvement_recommendations: list[dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "repository": self.repository,
            "overall_score": round(self.overall_score, 2),
            "status": self.status,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "trend": [t.to_dict() for t in self.trend],
            "improvement_recommendations": list(self.improvement_recommendations),
            "generated_at": self.generated_at.isoformat(),
        }


class RepositoryHealthCenter:
    """Phase 23 — Repository Health Center.

    Each dimension delegates to the appropriate engine or performs a focused
    scan. The Health Center is the single pane of glass for repository health.
    """

    def __init__(self, repo_root: str | Path = ".") -> None:
        self._root = Path(repo_root)
        self._history: list[HealthTrend] = []

    # --- public API -----------------------------------------------------

    async def assess(self) -> HealthReport:
        """Run a full health assessment."""
        report = HealthReport(repository=str(self._root))
        report.dimensions = [
            await self._assess_repository(),
            await self._assess_architecture(),
            await self._assess_dependency(),
            await self._assess_documentation(),
            await self._assess_security(),
            await self._assess_testing(),
            await self._assess_release(),
            await self._assess_knowledge(),
        ]
        # Overall score: weighted average
        weights = {
            HealthDimension.REPOSITORY.value: 0.10,
            HealthDimension.ARCHITECTURE.value: 0.15,
            HealthDimension.DEPENDENCY.value: 0.10,
            HealthDimension.DOCUMENTATION.value: 0.10,
            HealthDimension.SECURITY.value: 0.20,
            HealthDimension.TESTING.value: 0.15,
            HealthDimension.RELEASE.value: 0.10,
            HealthDimension.KNOWLEDGE.value: 0.10,
        }
        total_weight = sum(weights.values())
        weighted = sum(d.score * weights.get(d.dimension, 0) for d in report.dimensions)
        report.overall_score = weighted / total_weight if total_weight else 0.0
        if report.overall_score >= 80:
            report.status = "healthy"
        elif report.overall_score >= 50:
            report.status = "warning"
        else:
            report.status = "critical"
        # Record trend
        trend_point = HealthTrend(
            overall_score=report.overall_score,
            by_dimension={d.dimension: d.score for d in report.dimensions},
        )
        self._history.append(trend_point)
        report.trend = list(self._history[-12:])
        # Improvement recommendations
        report.improvement_recommendations = self._improvements(report.dimensions)
        return report

    async def quick_score(self) -> float:
        """Return only the overall health score (0..100)."""
        report = await self.assess()
        return report.overall_score

    # --- per-dimension assessments -------------------------------------

    async def _assess_repository(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.REPOSITORY.value,
            confidence=0.85,
        )
        py_files = list(self._root.rglob("*.py"))
        py_files = [p for p in py_files if not any(
            seg in p.parts for seg in (".venv", "node_modules", ".git", "__pycache__", "build", "dist")
        )]
        has_readme = (self._root / "README.md").exists()
        has_license = (self._root / "LICENSE").exists()
        has_pyproject = (self._root / "pyproject.toml").exists()
        has_git = (self._root / ".git").exists()
        score = 0.0
        indicators: dict[str, Any] = {}
        if has_readme:
            score += 25
            indicators["readme"] = True
        if has_license:
            score += 25
            indicators["license"] = True
        if has_pyproject:
            score += 25
            indicators["pyproject"] = True
        if has_git:
            score += 25
            indicators["git"] = True
        indicators["python_files"] = len(py_files)
        result.score = score
        result.status = "healthy" if score >= 75 else ("warning" if score >= 50 else "critical")
        result.summary = f"Repository has {len(py_files)} Python files; structural completeness {score:.0f}/100."
        result.indicators = indicators
        result.recommendation = "Ensure README, LICENSE, pyproject.toml, and .git are all present."
        return result

    async def _assess_architecture(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.ARCHITECTURE.value,
            confidence=0.7,
        )
        # Count layer-direction violations
        violations = 0
        for p in self._root.rglob("*.py"):
            if any(seg in p.parts for seg in (".venv", "node_modules", "__pycache__", "build", "dist")):
                continue
            if "services" in p.parts or "core" in p.parts:
                src = p.read_text(encoding="utf-8", errors="ignore")
                for line in src.splitlines():
                    s = line.strip()
                    if s.startswith("from surfaces") or s.startswith("import surfaces"):
                        violations += 1
        score = max(0.0, 100.0 - violations * 10)
        result.score = score
        result.status = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")
        result.summary = f"{violations} layer-direction violations."
        result.indicators = {"violations": violations}
        result.recommendation = "Enforce dependency direction via CI linting."
        return result

    async def _assess_dependency(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.DEPENDENCY.value,
            confidence=0.75,
        )
        pyproject = self._root / "pyproject.toml"
        if not pyproject.exists():
            result.score = 30.0
            result.status = "critical"
            result.summary = "No pyproject.toml found."
            return result
        src = pyproject.read_text(encoding="utf-8", errors="ignore")
        in_deps = False
        dep_count = 0
        for line in src.splitlines():
            if "dependencies = [" in line:
                in_deps = True
                continue
            if in_deps:
                if line.strip() == "]":
                    in_deps = False
                    continue
                if line.strip().strip(",").strip("\"'"):
                    dep_count += 1
        score = max(0.0, 100.0 - max(0, dep_count - 50) * 1.5)
        result.score = score
        result.status = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")
        result.summary = f"{dep_count} dependencies."
        result.indicators = {"dependency_count": dep_count}
        result.recommendation = "Run pip-audit and prune unused dependencies."
        return result

    async def _assess_documentation(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.DOCUMENTATION.value,
            confidence=0.8,
        )
        must_have = ["README.md", "CHANGELOG.md", "LICENSE"]
        missing = [m for m in must_have if not (self._root / m).exists()]
        docs_dir = self._root / "docs"
        doc_count = len(list(docs_dir.rglob("*.md"))) if docs_dir.exists() else 0
        score = 100.0 - len(missing) * 20 - (10 if doc_count < 5 else 0)
        score = max(0.0, score)
        result.score = score
        result.status = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")
        result.summary = f"{len(missing)} must-have docs missing; {doc_count} docs in docs/."
        result.indicators = {"missing": missing, "doc_count": doc_count}
        result.recommendation = "Fill documentation gaps and keep CHANGELOG current."
        return result

    async def _assess_security(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.SECURITY.value,
            confidence=0.75,
        )
        dangerous = 0
        for p in self._root.rglob("*.py"):
            if any(seg in p.parts for seg in (".venv", "node_modules", "__pycache__", "build", "dist", "tests")):
                continue
            src = p.read_text(encoding="utf-8", errors="ignore")
            for line in src.splitlines():
                if ("eval(" in line or "exec(" in line) and not line.strip().startswith("#"):
                    dangerous += 1
        score = max(0.0, 100.0 - dangerous * 15)
        result.score = score
        result.status = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")
        result.summary = f"{dangerous} dangerous patterns (eval/exec)."
        result.indicators = {"dangerous_patterns": dangerous}
        result.recommendation = "Run bandit in CI and remove all eval/exec usage."
        return result

    async def _assess_testing(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.TESTING.value,
            confidence=0.8,
        )
        tests_dir = self._root / "tests"
        if not tests_dir.exists():
            result.score = 0.0
            result.status = "critical"
            result.summary = "No tests directory."
            return result
        test_count = sum(1 for _ in tests_dir.rglob("test_*.py"))
        py_files = [p for p in self._root.rglob("*.py")
                    if "tests" not in p.parts and not any(
                        seg in p.parts for seg in (".venv", "node_modules", "__pycache__", "build", "dist")
                    )]
        ratio = test_count / max(1, len(py_files))
        score = min(100.0, ratio * 100)
        result.score = score
        result.status = "healthy" if score >= 60 else ("warning" if score >= 30 else "critical")
        result.summary = f"{test_count} test files; ratio={ratio:.2f}."
        result.indicators = {"test_count": test_count, "test_to_source_ratio": ratio}
        result.recommendation = "Grow tests until test-to-source ratio is at least 0.5."
        return result

    async def _assess_release(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.RELEASE.value,
            confidence=0.7,
        )
        has_changelog = (self._root / "CHANGELOG.md").exists()
        has_release_notes = any(self._root.rglob("RELEASE_NOTES*.md"))
        workflows_dir = self._root / ".github" / "workflows"
        has_release_workflow = False
        if workflows_dir.exists():
            for wf in workflows_dir.glob("*.yml"):
                if "release" in wf.name.lower():
                    has_release_workflow = True
                    break
        score = 0.0
        if has_changelog:
            score += 40
        if has_release_notes:
            score += 30
        if has_release_workflow:
            score += 30
        result.score = score
        result.status = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")
        result.summary = (
            f"changelog={has_changelog}, release_notes={has_release_notes}, "
            f"release_workflow={has_release_workflow}."
        )
        result.indicators = {
            "changelog": has_changelog,
            "release_notes": has_release_notes,
            "release_workflow": has_release_workflow,
        }
        result.recommendation = "Add a release workflow that automates CHANGELOG and tag creation."
        return result

    async def _assess_knowledge(self) -> HealthDimensionResult:
        result = HealthDimensionResult(
            dimension=HealthDimension.KNOWLEDGE.value,
            confidence=0.65,
        )
        # Knowledge health = docs/ directory + ADRs + knowledge base
        docs_dir = self._root / "docs"
        adr_count = 0
        if docs_dir.exists():
            adr_count = sum(1 for _ in docs_dir.rglob("ADR*.md"))
            adr_count += sum(1 for _ in docs_dir.rglob("adr-*.md"))
        knowledge_dir = self._root / "knowledge"
        has_knowledge_base = knowledge_dir.exists()
        score = 30.0  # base
        if adr_count > 0:
            score += min(40.0, adr_count * 5)
        if has_knowledge_base:
            score += 30.0
        result.score = min(score, 100.0)
        result.status = "healthy" if score >= 70 else ("warning" if score >= 40 else "critical")
        result.summary = f"{adr_count} ADRs; knowledge_base={has_knowledge_base}."
        result.indicators = {"adr_count": adr_count, "has_knowledge_base": has_knowledge_base}
        result.recommendation = "Record major decisions as ADRs and curate a knowledge base."
        return result

    # --- improvements ---------------------------------------------------

    def _improvements(
        self, dimensions: list[HealthDimensionResult]
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for d in dimensions:
            if d.status == "critical":
                out.append({
                    "dimension": d.dimension,
                    "priority": "high",
                    "current_score": d.score,
                    "target_score": 80.0,
                    "recommendation": d.recommendation,
                    "confidence": d.confidence,
                    "requires_approval": True,
                })
            elif d.status == "warning":
                out.append({
                    "dimension": d.dimension,
                    "priority": "medium",
                    "current_score": d.score,
                    "target_score": 90.0,
                    "recommendation": d.recommendation,
                    "confidence": d.confidence,
                    "requires_approval": True,
                })
        out.sort(key=lambda x: x["current_score"])
        return out
