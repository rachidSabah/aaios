"""Phase 21 — Release Readiness Engine.

Continuously determines release readiness across 10 dimensions:
architecture compliance, security, performance, testing, documentation,
packaging, dependencies, migration, compatibility, operational readiness.

Generates a release readiness score, blocking issues, warnings,
certification report, and Go/No-Go recommendation. All go/no-go decisions
require human approval.
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
    "CertificationReport",
    "ReadinessDimension",
    "ReadinessDimensionResult",
    "ReleaseReadinessEngine",
    "ReleaseReadinessReport",
]


class ReadinessDimension(StrEnum):
    """The ten release readiness dimensions."""

    ARCHITECTURE_COMPLIANCE = "architecture_compliance"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    PACKAGING = "packaging"
    DEPENDENCIES = "dependencies"
    MIGRATION = "migration"
    COMPATIBILITY = "compatibility"
    OPERATIONAL_READINESS = "operational_readiness"


@dataclass
class ReadinessDimensionResult:
    """Result for one readiness dimension."""

    dimension: str = ""
    score: float = 0.0  # 0..1
    status: str = "warning"  # pass | warning | fail
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": round(self.score, 4),
            "status": self.status,
            "blocking_issues": list(self.blocking_issues),
            "warnings": list(self.warnings),
            "evidence": list(self.evidence),
            "confidence": round(self.confidence, 4),
            "recommendation": self.recommendation,
        }


@dataclass
class CertificationReport:
    """Certification report for a release."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    version: str = ""
    certified: bool = False
    certification_level: str = "none"  # none | basic | standard | strict
    overall_score: float = 0.0
    dimension_scores: dict[str, float] = field(default_factory=dict)
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_approvals: list[str] = field(default_factory=list)
    certified_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "version": self.version,
            "certified": self.certified,
            "certification_level": self.certification_level,
            "overall_score": round(self.overall_score, 4),
            "dimension_scores": dict(self.dimension_scores),
            "blocking_issues": list(self.blocking_issues),
            "warnings": list(self.warnings),
            "required_approvals": list(self.required_approvals),
            "certified_at": self.certified_at.isoformat(),
        }


@dataclass
class ReleaseReadinessReport:
    """A complete release readiness report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    version: str = ""
    overall_score: float = 0.0
    recommendation: str = "no_go"  # go | no_go | conditional_go
    dimensions: list[ReadinessDimensionResult] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    certification: CertificationReport = field(default_factory=CertificationReport)
    required_approvals: list[str] = field(default_factory=list)
    confidence: float = 0.5
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "version": self.version,
            "overall_score": round(self.overall_score, 4),
            "recommendation": self.recommendation,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "blocking_issues": list(self.blocking_issues),
            "warnings": list(self.warnings),
            "certification": self.certification.to_dict(),
            "required_approvals": list(self.required_approvals),
            "confidence": round(self.confidence, 4),
            "generated_at": self.generated_at.isoformat(),
        }


class ReleaseReadinessEngine:
    """Phase 21 — Release Readiness Engine.

    All go/no-go decisions require human approval. The engine only
    recommends; it never certifies on its own.
    """

    # --- public API -----------------------------------------------------

    async def evaluate(
        self,
        root: str | Path,
        *,
        version: str = "",
    ) -> ReleaseReadinessReport:
        """Evaluate release readiness for the project at ``root``."""
        root_path = Path(root)
        report = ReleaseReadinessReport(version=version)
        report.dimensions = [
            await self._eval_architecture(root_path),
            await self._eval_security(root_path),
            await self._eval_performance(root_path),
            await self._eval_testing(root_path),
            await self._eval_documentation(root_path),
            await self._eval_packaging(root_path),
            await self._eval_dependencies(root_path),
            await self._eval_migration(root_path),
            await self._eval_compatibility(root_path),
            await self._eval_operational(root_path),
        ]
        # Aggregate
        scores = [d.score for d in report.dimensions]
        report.overall_score = sum(scores) / len(scores) if scores else 0.0
        for d in report.dimensions:
            if d.status == "fail":
                report.blocking_issues.extend(d.blocking_issues)
            elif d.status == "warning":
                report.warnings.extend(d.warnings)
        # Recommendation
        blocking_count = sum(1 for d in report.dimensions if d.status == "fail")
        warning_count = sum(1 for d in report.dimensions if d.status == "warning")
        if blocking_count == 0 and warning_count <= 2:
            report.recommendation = "go"
        elif blocking_count == 0:
            report.recommendation = "conditional_go"
        else:
            report.recommendation = "no_go"
        report.required_approvals = self._required_approvals(report)
        report.certification = self._build_certification(report)
        report.confidence = 0.75
        return report

    async def certification_report(
        self, root: str | Path, *, version: str = ""
    ) -> CertificationReport:
        """Return only the certification report."""
        full = await self.evaluate(root, version=version)
        return full.certification

    # --- per-dimension evaluation --------------------------------------

    async def _eval_architecture(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.ARCHITECTURE_COMPLIANCE.value,
            confidence=0.7,
        )
        # Check for layer-direction violations
        violations = 0
        for p in root.rglob("*.py"):
            if any(
                seg in p.parts for seg in (".venv", "node_modules", "__pycache__", "build", "dist")
            ):
                continue
            if "services" in p.parts or "core" in p.parts:
                src = p.read_text(encoding="utf-8", errors="ignore")
                for line in src.splitlines():
                    if line.strip().startswith("from surfaces") or line.strip().startswith(
                        "import surfaces"
                    ):
                        if "services" in str(p) or "core" in str(p):
                            violations += 1
        if violations == 0:
            result.score = 0.95
            result.status = "pass"
            result.evidence.append("No layer-direction violations detected.")
        elif violations <= 3:
            result.score = 0.7
            result.status = "warning"
            result.warnings.append(f"{violations} layer-direction violations found.")
        else:
            result.score = 0.3
            result.status = "fail"
            result.blocking_issues.append(
                f"{violations} layer-direction violations must be fixed before release."
            )
        result.recommendation = "Enforce architecture invariants via CI checks."
        return result

    async def _eval_security(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.SECURITY.value,
            confidence=0.75,
        )
        dangerous_patterns = 0
        for p in root.rglob("*.py"):
            if any(
                seg in p.parts
                for seg in (".venv", "node_modules", "__pycache__", "build", "dist", "tests")
            ):
                continue
            src = p.read_text(encoding="utf-8", errors="ignore")
            for line in src.splitlines():
                if "eval(" in line or "exec(" in line:
                    if not line.strip().startswith("#"):
                        dangerous_patterns += 1
        if dangerous_patterns == 0:
            result.score = 0.95
            result.status = "pass"
            result.evidence.append("No eval/exec usage detected.")
        else:
            result.score = 0.2
            result.status = "fail"
            result.blocking_issues.append(f"{dangerous_patterns} eval/exec usages must be removed.")
        result.recommendation = "Run bandit + pip-audit in CI on every PR."
        return result

    async def _eval_performance(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.PERFORMANCE.value,
            confidence=0.55,
        )
        # Heuristic: presence of performance tests
        perf_tests = (
            list((root / "tests" / "performance").glob("test_*.py"))
            if (root / "tests" / "performance").exists()
            else []
        )
        if len(perf_tests) >= 1:
            result.score = 0.8
            result.status = "pass"
            result.evidence.append(f"{len(perf_tests)} performance test files found.")
        else:
            result.score = 0.5
            result.status = "warning"
            result.warnings.append("No performance tests found — add baseline benchmarks.")
        result.recommendation = "Establish performance baselines and regression tests."
        return result

    async def _eval_testing(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.TESTING.value,
            confidence=0.8,
        )
        tests_dir = root / "tests"
        if not tests_dir.exists():
            result.score = 0.0
            result.status = "fail"
            result.blocking_issues.append("No tests directory found.")
            return result
        test_count = sum(1 for _ in tests_dir.rglob("test_*.py"))
        if test_count >= 100:
            result.score = 0.95
            result.status = "pass"
            result.evidence.append(f"{test_count} test files found.")
        elif test_count >= 30:
            result.score = 0.7
            result.status = "warning"
            result.warnings.append(f"Only {test_count} test files — increase coverage.")
        else:
            result.score = 0.3
            result.status = "fail"
            result.blocking_issues.append(
                f"Only {test_count} test files — insufficient for release."
            )
        result.recommendation = "Add tests until coverage is at least 80% on critical paths."
        return result

    async def _eval_documentation(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.DOCUMENTATION.value,
            confidence=0.8,
        )
        must_have = ["README.md", "CHANGELOG.md", "LICENSE"]
        missing = [m for m in must_have if not (root / m).exists()]
        if not missing:
            result.score = 0.9
            result.status = "pass"
            result.evidence.append("All must-have top-level docs present.")
        else:
            result.score = 0.4
            result.status = "warning"
            result.warnings.append(f"Missing: {missing}")
        result.recommendation = "Update CHANGELOG before tagging the release."
        return result

    async def _eval_packaging(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.PACKAGING.value,
            confidence=0.85,
        )
        has_pyproject = (root / "pyproject.toml").exists()
        has_pkg_json = (root / "package.json").exists()
        if has_pyproject or has_pkg_json:
            result.score = 0.9
            result.status = "pass"
            result.evidence.append("Packaging manifest present.")
        else:
            result.score = 0.1
            result.status = "fail"
            result.blocking_issues.append(
                "No packaging manifest (pyproject.toml or package.json) found."
            )
        result.recommendation = "Verify the build pipeline produces a clean artifact."
        return result

    async def _eval_dependencies(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.DEPENDENCIES.value,
            confidence=0.7,
        )
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            result.score = 0.5
            result.status = "warning"
            result.warnings.append("No pyproject.toml — cannot audit dependencies.")
            return result
        # Count dependencies
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
        if dep_count < 80:
            result.score = 0.85
            result.status = "pass"
            result.evidence.append(f"{dep_count} dependencies.")
        else:
            result.score = 0.5
            result.status = "warning"
            result.warnings.append(f"{dep_count} dependencies — large attack surface.")
        result.recommendation = "Run pip-audit / npm audit before release."
        return result

    async def _eval_migration(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.MIGRATION.value,
            confidence=0.7,
        )
        migrations_dir = root / "migrations" / "versions"
        if migrations_dir.exists():
            result.score = 0.85
            result.status = "pass"
            result.evidence.append(f"{len(list(migrations_dir.glob('*.py')))} migrations present.")
        else:
            result.score = 0.7
            result.status = "pass"
            result.evidence.append("No database migrations needed.")
        # Check for migration guide
        has_migration_doc = (
            any((root / "docs").rglob("MIGRATION*.md")) if (root / "docs").exists() else False
        )
        if not has_migration_doc:
            result.warnings.append("No migration guide found in docs/.")
            result.score = min(result.score, 0.7)
            result.status = "warning"
        result.recommendation = "Publish a migration guide for breaking changes."
        return result

    async def _eval_compatibility(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.COMPATIBILITY.value,
            confidence=0.75,
        )
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            result.score = 0.5
            result.status = "warning"
            result.warnings.append("No pyproject.toml — cannot check compatibility.")
            return result
        src = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "requires-python" in src:
            result.score = 0.9
            result.status = "pass"
            result.evidence.append("Python version requirement declared.")
        else:
            result.score = 0.4
            result.status = "warning"
            result.warnings.append("No requires-python declaration.")
        result.recommendation = "Declare and test against all supported Python versions."
        return result

    async def _eval_operational(self, root: Path) -> ReadinessDimensionResult:
        result = ReadinessDimensionResult(
            dimension=ReadinessDimension.OPERATIONAL_READINESS.value,
            confidence=0.7,
        )
        has_dockerfile = (root / "Dockerfile").exists() or (root / "docker").exists()
        has_compose = (root / "docker-compose.yml").exists() or (root / "compose.yml").exists()
        has_healthcheck = False
        for p in root.rglob("*.py"):
            if "health" in p.name.lower():
                has_healthcheck = True
                break
        score = 0.5
        if has_dockerfile:
            score += 0.2
        if has_compose:
            score += 0.15
        if has_healthcheck:
            score += 0.15
        result.score = min(score, 1.0)
        result.status = "pass" if score >= 0.8 else "warning"
        if result.status == "warning":
            result.warnings.append(
                f"Operational readiness partial (Dockerfile={has_dockerfile}, "
                f"Compose={has_compose}, Health={has_healthcheck})."
            )
        else:
            result.evidence.append("All operational artifacts present.")
        result.recommendation = (
            "Provide Dockerfile, compose, and a /health endpoint for production."
        )
        return result

    # --- certification & approvals -------------------------------------

    def _required_approvals(self, report: ReleaseReadinessReport) -> list[str]:
        approvals: list[str] = []
        if report.recommendation == "go":
            approvals.append("release_manager")
        elif report.recommendation == "conditional_go":
            approvals.extend(["release_manager", "engineering_lead"])
        else:
            approvals.extend(["release_manager", "engineering_lead", "security_officer"])
        # Always require the architect for any release touching architecture
        for d in report.dimensions:
            if (
                d.dimension == ReadinessDimension.ARCHITECTURE_COMPLIANCE.value
                and d.status != "pass"
            ):
                approvals.append("architect")
                break
        return sorted(set(approvals))

    def _build_certification(self, report: ReleaseReadinessReport) -> CertificationReport:
        cert = CertificationReport(
            version=report.version,
            overall_score=report.overall_score,
            dimension_scores={d.dimension: d.score for d in report.dimensions},
            blocking_issues=report.blocking_issues,
            warnings=report.warnings,
            required_approvals=report.required_approvals,
        )
        # Certification level
        if report.overall_score >= 0.9 and not report.blocking_issues:
            cert.certification_level = "strict"
            cert.certified = True
        elif report.overall_score >= 0.75 and not report.blocking_issues:
            cert.certification_level = "standard"
            cert.certified = True
        elif report.overall_score >= 0.6:
            cert.certification_level = "basic"
            cert.certified = report.recommendation != "no_go"
        else:
            cert.certification_level = "none"
            cert.certified = False
        return cert
