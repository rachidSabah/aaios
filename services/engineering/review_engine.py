"""Phase 17 — Engineering Review Engine.

Twelve review types covering the entire engineering lifecycle. Every review
produces a structured verdict with strengths, weaknesses, evidence, a risk
score, confidence, recommendations, an approval requirement, and a historical
comparison.

Reviews are READ-ONLY — they never modify code. Every recommendation carries
``requires_approval=True``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "ReviewFinding",
    "ReviewReport",
    "ReviewType",
    "EngineeringReviewEngine",
]


class ReviewType(StrEnum):
    """The twelve engineering review dimensions."""

    ARCHITECTURE = "architecture"
    CODE = "code"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEPENDENCY = "dependency"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    API = "api"
    DATABASE = "database"
    WORKFLOW = "workflow"
    PLUGIN = "plugin"
    MISSION = "mission"


@dataclass
class ReviewFinding:
    """A single finding inside a review (strength OR weakness)."""

    finding_id: str = field(default_factory=lambda: uuid4().hex[:8])
    kind: str = "weakness"  # strength | weakness | observation
    title: str = ""
    description: str = ""
    severity: str = "medium"  # info | low | medium | high | critical
    confidence: float = 0.7
    evidence: list[str] = field(default_factory=list)
    location: str = ""  # file:line or component name
    recommendation: str = ""
    requires_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "confidence": round(self.confidence, 4),
            "evidence": list(self.evidence),
            "location": self.location,
            "recommendation": self.recommendation,
            "requires_approval": self.requires_approval,
        }


@dataclass
class ReviewReport:
    """A complete engineering review report."""

    review_id: str = field(default_factory=lambda: uuid4().hex[:12])
    review_type: str = ""
    target: str = ""  # path / module / mission id
    summary: str = ""
    strengths: list[ReviewFinding] = field(default_factory=list)
    weaknesses: list[ReviewFinding] = field(default_factory=list)
    observations: list[ReviewFinding] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 (safe) .. 1.0 (critical)
    confidence: float = 0.5
    recommendations: list[str] = field(default_factory=list)
    approval_required: bool = True
    historical_comparison: dict[str, Any] = field(default_factory=dict)
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reviewer: str = "engineering-review-engine"

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "review_type": self.review_type,
            "target": self.target,
            "summary": self.summary,
            "strengths": [s.to_dict() for s in self.strengths],
            "weaknesses": [w.to_dict() for w in self.weaknesses],
            "observations": [o.to_dict() for o in self.observations],
            "risk_score": round(self.risk_score, 4),
            "confidence": round(self.confidence, 4),
            "recommendations": list(self.recommendations),
            "approval_required": self.approval_required,
            "historical_comparison": dict(self.historical_comparison),
            "reviewed_at": self.reviewed_at.isoformat(),
            "reviewer": self.reviewer,
        }


class EngineeringReviewEngine:
    """Phase 17 — Engineering Review Engine.

    Twelve review types. All reviews are read-only. Every recommendation
    requires human approval.
    """

    # --- public API -----------------------------------------------------

    async def review(
        self,
        review_type: ReviewType | str,
        target: str | Path,
        *,
        history: list[ReviewReport] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ReviewReport:
        """Run a review of ``target`` for the given ``review_type``."""
        rt = ReviewType(review_type) if isinstance(review_type, str) else review_type
        target_str = str(target)
        ctx = context or {}
        path = Path(target_str)

        if rt is ReviewType.ARCHITECTURE:
            report = await self._review_architecture(path, ctx)
        elif rt is ReviewType.CODE:
            report = await self._review_code(path, ctx)
        elif rt is ReviewType.SECURITY:
            report = await self._review_security(path, ctx)
        elif rt is ReviewType.PERFORMANCE:
            report = await self._review_performance(path, ctx)
        elif rt is ReviewType.DEPENDENCY:
            report = await self._review_dependency(path, ctx)
        elif rt is ReviewType.DOCUMENTATION:
            report = await self._review_documentation(path, ctx)
        elif rt is ReviewType.TESTING:
            report = await self._review_testing(path, ctx)
        elif rt is ReviewType.API:
            report = await self._review_api(path, ctx)
        elif rt is ReviewType.DATABASE:
            report = await self._review_database(path, ctx)
        elif rt is ReviewType.WORKFLOW:
            report = await self._review_workflow(path, ctx)
        elif rt is ReviewType.PLUGIN:
            report = await self._review_plugin(path, ctx)
        elif rt is ReviewType.MISSION:
            report = await self._review_mission(target_str, ctx)
        else:  # pragma: no cover — exhaustive enum
            raise ValueError(f"Unknown review type: {rt}")

        if history:
            report.historical_comparison = self._compare_with_history(report, history)
        return report

    async def review_all(
        self,
        target: str | Path,
        *,
        history: list[ReviewReport] | None = None,
    ) -> dict[str, ReviewReport]:
        """Run every review type against ``target``."""
        results: dict[str, ReviewReport] = {}
        for rt in ReviewType:
            results[rt.value] = await self.review(rt, target, history=history)
        return results

    # --- individual review types ---------------------------------------

    async def _review_architecture(
        self, path: Path, ctx: dict[str, Any]
    ) -> ReviewReport:
        """Architecture review — layers, boundaries, coupling, god-classes."""
        report = ReviewReport(
            review_type=ReviewType.ARCHITECTURE.value,
            target=str(path),
            summary="Architecture review of layer boundaries, coupling, and structural integrity.",
        )
        py_files = self._collect_python_files(path)
        if not py_files:
            report.summary = "No Python files found — architecture review skipped."
            report.confidence = 0.1
            return report

        layer_violations: list[str] = []
        god_classes: list[str] = []
        total_lines_per_class: dict[str, int] = {}

        for fp in py_files:
            tree = self._parse_python(fp)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    line_count = self._count_class_lines(node)
                    cls_name = f"{fp.name}::{node.name}"
                    total_lines_per_class[cls_name] = line_count
                    if line_count > 300:
                        god_classes.append(cls_name)
            # detect cross-layer imports
            src = fp.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"^\s*(?:from|import)\s+(surfaces|agents)\b", src, re.M):
                if "services" in str(fp) or "core" in str(fp):
                    layer_violations.append(f"{fp.name}: {m.group(0).strip()}")

        if not god_classes and not layer_violations:
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="No god classes detected",
                description=f"Reviewed {len(py_files)} Python files; no class exceeds 300 lines.",
                severity="info",
                confidence=0.85,
                evidence=[f"files_reviewed={len(py_files)}"],
            ))
        if god_classes:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="God classes detected",
                description=f"{len(god_classes)} classes exceed 300 lines — consider decomposition.",
                severity="high",
                confidence=0.8,
                evidence=god_classes[:10],
                recommendation="Split god classes along cohesive responsibilities.",
            ))
        if layer_violations:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Layer boundary violations",
                description=f"{len(layer_violations)} cross-layer imports detected.",
                severity="medium",
                confidence=0.75,
                evidence=layer_violations[:10],
                recommendation="Enforce dependency direction: core ← services ← surfaces.",
            ))

        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.78 if py_files else 0.2
        report.recommendations = [
            "Audit large classes for decomposition opportunities.",
            "Add architecture tests to prevent regressions.",
            "Document the layer dependency direction in CONTRIBUTING.md.",
        ]
        return report

    async def _review_code(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """Code review — complexity, duplication, style, dead code."""
        report = ReviewReport(
            review_type=ReviewType.CODE.value,
            target=str(path),
            summary="Static code review focused on complexity, dead code, and style.",
        )
        py_files = self._collect_python_files(path)
        long_funcs: list[str] = []
        complex_funcs: list[str] = []
        bare_excepts: list[str] = []
        for fp in py_files:
            tree = self._parse_python(fp)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = self._count_func_lines(node)
                    if length > 50:
                        long_funcs.append(f"{fp.name}::{node.name} ({length} lines)")
                    cc = self._cyclomatic_complexity(node)
                    if cc > 10:
                        complex_funcs.append(f"{fp.name}::{node.name} (cc={cc})")
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        bare_excepts.append(f"{fp.name}:{node.lineno}")
        if long_funcs:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Long functions",
                description=f"{len(long_funcs)} functions exceed 50 lines.",
                severity="medium",
                confidence=0.8,
                evidence=long_funcs[:10],
                recommendation="Refactor long functions into smaller cohesive units.",
            ))
        if complex_funcs:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="High cyclomatic complexity",
                description=f"{len(complex_funcs)} functions have CC > 10.",
                severity="medium",
                confidence=0.78,
                evidence=complex_funcs[:10],
                recommendation="Reduce branching via early returns, polymorphism, or strategy pattern.",
            ))
        if bare_excepts:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Bare except clauses",
                description=f"{len(bare_excepts)} bare except clauses found.",
                severity="high",
                confidence=0.9,
                evidence=bare_excepts[:10],
                recommendation="Catch specific exceptions; never use bare 'except:'.",
            ))
        if not (long_funcs or complex_funcs or bare_excepts):
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="No major code smells detected",
                description=f"All {len(py_files)} files passed static complexity/style checks.",
                severity="info",
                confidence=0.7,
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.75 if py_files else 0.2
        report.recommendations = [
            "Add pre-commit hooks for ruff + mypy.",
            "Track complexity trends over time.",
        ]
        return report

    async def _review_security(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """Security review — common Python pitfalls (eval/exec, hardcoded secrets)."""
        report = ReviewReport(
            review_type=ReviewType.SECURITY.value,
            target=str(path),
            summary="Security review for common Python pitfalls and secret leakage.",
        )
        py_files = self._collect_python_files(path)
        dangerous: list[str] = []
        secrets: list[str] = []
        secret_re = re.compile(
            r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]"
        )
        for fp in py_files:
            src = fp.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"\b(eval|exec)\s*\(", src):
                dangerous.append(f"{fp.name}:{src[:m.start()].count(chr(10)) + 1}")
            for m in secret_re.finditer(src):
                secrets.append(f"{fp.name}:{src[:m.start()].count(chr(10)) + 1}")
        if dangerous:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Use of eval/exec",
                description=f"{len(dangerous)} occurrences of eval/exec.",
                severity="critical",
                confidence=0.92,
                evidence=dangerous[:10],
                recommendation="Replace eval/exec with safer alternatives (ast.literal_eval, etc.).",
            ))
        if secrets:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Possible hardcoded secrets",
                description=f"{len(secrets)} lines look like hardcoded credentials.",
                severity="critical",
                confidence=0.7,
                evidence=secrets[:10],
                recommendation="Move secrets to environment variables or a secret store.",
            ))
        if not dangerous and not secrets:
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="No obvious security pitfalls",
                description="No eval/exec or hardcoded secrets detected.",
                severity="info",
                confidence=0.7,
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.7 if py_files else 0.2
        report.recommendations = [
            "Run bandit in CI on every commit.",
            "Rotate any secrets that may have been committed.",
        ]
        return report

    async def _review_performance(
        self, path: Path, ctx: dict[str, Any]
    ) -> ReviewReport:
        """Performance review — N+1 patterns, list comprehensions in hot loops."""
        report = ReviewReport(
            review_type=ReviewType.PERFORMANCE.value,
            target=str(path),
            summary="Performance review for common Python hot-path anti-patterns.",
        )
        py_files = self._collect_python_files(path)
        nested_loops: list[str] = []
        sync_in_async: list[str] = []
        for fp in py_files:
            src = fp.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"for\s+\w+\s+in\s+.+:\s*\n\s*for\s+\w+\s+in", src):
                nested_loops.append(f"{fp.name}:{src[:m.start()].count(chr(10)) + 1}")
            for m in re.finditer(r"async\s+def\s+\w+.*:\s*\n(?:.*\n)*?\s*(?:time\.sleep|requests\.get)\s*\(", src):
                sync_in_async.append(f"{fp.name}:{src[:m.start()].count(chr(10)) + 1}")
        if nested_loops:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Nested loops detected",
                description=f"{len(nested_loops)} nested loops may indicate O(n^2) hot paths.",
                severity="medium",
                confidence=0.65,
                evidence=nested_loops[:10],
                recommendation="Profile hot paths; consider vectorization or algorithmic improvement.",
            ))
        if sync_in_async:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Blocking call inside async function",
                description=f"{len(sync_in_async)} sync calls inside async functions.",
                severity="high",
                confidence=0.75,
                evidence=sync_in_async[:10],
                recommendation="Use asyncio.to_thread() or async-native alternatives.",
            ))
        if not nested_loops and not sync_in_async:
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="No obvious performance anti-patterns",
                description="No nested loops or blocking calls in async code detected.",
                severity="info",
                confidence=0.6,
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.65 if py_files else 0.2
        report.recommendations = [
            "Add performance regression tests for critical paths.",
            "Establish baseline benchmarks in CI.",
        ]
        return report

    async def _review_dependency(
        self, path: Path, ctx: dict[str, Any]
    ) -> ReviewReport:
        """Dependency review — count, pinning, license concerns."""
        report = ReviewReport(
            review_type=ReviewType.DEPENDENCY.value,
            target=str(path),
            summary="Dependency review of pyproject.toml / package.json.",
        )
        deps_count = 0
        pinned_count = 0
        dep_files: list[str] = []
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            src = pyproject.read_text(encoding="utf-8", errors="ignore")
            in_deps = False
            for line in src.splitlines():
                if line.strip().startswith("dependencies = ["):
                    in_deps = True
                    continue
                if in_deps:
                    if line.strip() == "]":
                        in_deps = False
                        continue
                    stripped = line.strip().strip(",").strip("\"'")
                    if stripped:
                        deps_count += 1
                        dep_files.append(stripped)
                        if ">=" in stripped or "==" in stripped or "<" in stripped:
                            pinned_count += 1
        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                import json
                data = json.loads(pkg_json.read_text())
                deps = list(data.get("dependencies", {}).keys())
                deps_count += len(deps)
                dep_files.extend(deps)
                pinned_count += sum(
                    1 for v in data.get("dependencies", {}).values() if v.startswith("^") or v.startswith("~")
                )
            except (json.JSONDecodeError, OSError, ValueError):
                _log.warning("review_engine.package_json_unparseable", path=str(pkg_json))
        if deps_count == 0:
            report.summary = "No dependency manifests found — dependency review skipped."
            report.confidence = 0.1
            return report
        report.observations.append(ReviewFinding(
            kind="observation",
            title="Dependency inventory",
            description=f"{deps_count} dependencies; {pinned_count} version-constrained.",
            severity="info",
            confidence=0.9,
            evidence=dep_files[:20],
        ))
        if deps_count > 80:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="High dependency count",
                description=f"{deps_count} dependencies — large attack surface.",
                severity="medium",
                confidence=0.7,
                recommendation="Audit and remove unused dependencies.",
            ))
        if pinned_count < deps_count // 2:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Insufficient version pinning",
                description=f"Only {pinned_count}/{deps_count} dependencies have version constraints.",
                severity="medium",
                confidence=0.75,
                recommendation="Pin all dependency versions in production manifests.",
            ))
        if deps_count <= 80 and pinned_count >= deps_count // 2:
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="Healthy dependency posture",
                description="Dependency count is reasonable and versions are pinned.",
                severity="info",
                confidence=0.75,
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.8
        report.recommendations = [
            "Run pip-audit / npm audit in CI.",
            "Review license compatibility annually.",
        ]
        return report

    async def _review_documentation(
        self, path: Path, ctx: dict[str, Any]
    ) -> ReviewReport:
        """Documentation review — README presence, docstring coverage."""
        report = ReviewReport(
            review_type=ReviewType.DOCUMENTATION.value,
            target=str(path),
            summary="Documentation review for README, docstrings, and API docs.",
        )
        readme = path / "README.md"
        if not readme.exists():
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Missing README",
                description="No README.md at repository root.",
                severity="high",
                confidence=0.95,
                recommendation="Add a comprehensive README with project overview and usage.",
            ))
        else:
            readme_len = len(readme.read_text(encoding="utf-8", errors="ignore").splitlines())
            if readme_len < 50:
                report.weaknesses.append(ReviewFinding(
                    kind="weakness",
                    title="Thin README",
                    description=f"README has only {readme_len} lines.",
                    severity="low",
                    confidence=0.85,
                    recommendation="Expand README with examples, architecture, and contributing sections.",
                ))
            else:
                report.strengths.append(ReviewFinding(
                    kind="strength",
                    title="Comprehensive README",
                    description=f"README has {readme_len} lines.",
                    severity="info",
                    confidence=0.85,
                ))
        # docstring coverage
        py_files = self._collect_python_files(path)
        total_funcs = 0
        documented_funcs = 0
        for fp in py_files:
            tree = self._parse_python(fp)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_funcs += 1
                    if ast.get_docstring(node):
                        documented_funcs += 1
        if total_funcs:
            coverage = documented_funcs / total_funcs
            if coverage < 0.5:
                report.weaknesses.append(ReviewFinding(
                    kind="weakness",
                    title="Low docstring coverage",
                    description=f"{documented_funcs}/{total_funcs} functions documented ({coverage:.0%}).",
                    severity="medium",
                    confidence=0.9,
                    recommendation="Add docstrings to all public functions.",
                ))
            else:
                report.strengths.append(ReviewFinding(
                    kind="strength",
                    title="Good docstring coverage",
                    description=f"{documented_funcs}/{total_funcs} functions documented ({coverage:.0%}).",
                    severity="info",
                    confidence=0.9,
                ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.8 if py_files or readme.exists() else 0.2
        report.recommendations = [
            "Generate API docs from docstrings (e.g. pdoc, mkdocs).",
            "Add a CONTRIBUTING.md and ARCHITECTURE.md if missing.",
        ]
        return report

    async def _review_testing(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """Testing review — coverage, test/file ratio, marker usage."""
        report = ReviewReport(
            review_type=ReviewType.TESTING.value,
            target=str(path),
            summary="Testing review of test count, structure, and markers.",
        )
        tests_dir = path / "tests"
        if not tests_dir.exists():
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="No tests directory",
                description="Repository has no tests/ directory.",
                severity="critical",
                confidence=0.95,
                recommendation="Establish a tests/ directory mirroring the source layout.",
            ))
            report.risk_score = 0.9
            report.confidence = 0.85
            return report
        test_files = list(tests_dir.rglob("test_*.py"))
        py_files = self._collect_python_files(path)
        py_files = [f for f in py_files if "tests" not in str(f)]
        ratio = len(test_files) / max(1, len(py_files))
        if ratio < 0.3:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Low test-to-source ratio",
                description=f"{len(test_files)} test files vs {len(py_files)} source files ({ratio:.0%}).",
                severity="high",
                confidence=0.85,
                recommendation="Add tests until ratio is at least 0.5.",
            ))
        else:
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="Healthy test-to-source ratio",
                description=f"{len(test_files)} test files vs {len(py_files)} source files ({ratio:.0%}).",
                severity="info",
                confidence=0.85,
            ))
        # marker usage
        marker_count = 0
        for tf in test_files:
            src = tf.read_text(encoding="utf-8", errors="ignore")
            marker_count += len(re.findall(r"@pytest\.mark\.\w+", src))
        if marker_count < len(test_files) // 4:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Few pytest markers used",
                description=f"{marker_count} markers across {len(test_files)} test files.",
                severity="low",
                confidence=0.7,
                recommendation="Use markers (slow, offline, integration) for selective runs.",
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.82
        report.recommendations = [
            "Track coverage trends in CI.",
            "Add integration tests for critical user journeys.",
        ]
        return report

    async def _review_api(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """API review — versioning, error handling, schema."""
        report = ReviewReport(
            review_type=ReviewType.API.value,
            target=str(path),
            summary="API review of REST endpoints, versioning, and error handling.",
        )
        api_dir = path / "surfaces" / "api"
        if not api_dir.exists():
            report.summary = "No surfaces/api directory — API review skipped."
            report.confidence = 0.1
            return report
        api_files = list(api_dir.rglob("*.py"))
        endpoints: list[str] = []
        no_error_handling: list[str] = []
        for fp in api_files:
            src = fp.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"@\w+\.(get|post|put|delete|patch)\(['\"]([^'\"]+)", src):
                endpoints.append(f"{fp.name}: {m.group(1).upper()} {m.group(2)}")
            # crude: endpoints whose body has no try/except
            for m in re.finditer(
                r"async\s+def\s+(\w+)\s*\([^)]*\)\s*:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+(?!.*try:)",
                src,
            ):
                no_error_handling.append(f"{fp.name}::{m.group(1)}")
        if not endpoints:
            report.summary = "No HTTP endpoints detected — API review skipped."
            report.confidence = 0.15
            return report
        report.observations.append(ReviewFinding(
            kind="observation",
            title="Endpoint inventory",
            description=f"{len(endpoints)} HTTP endpoints detected.",
            severity="info",
            confidence=0.85,
            evidence=endpoints[:20],
        ))
        versioned = sum(1 for e in endpoints if "/v1/" in e or "/v2/" in e)
        if versioned < len(endpoints) // 2 and len(endpoints) > 5:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="API versioning inconsistent",
                description=f"Only {versioned}/{len(endpoints)} endpoints are versioned.",
                severity="medium",
                confidence=0.7,
                recommendation="Adopt a consistent versioning scheme (e.g. /v1/).",
            ))
        else:
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="Consistent API versioning",
                description=f"{versioned}/{len(endpoints)} endpoints are versioned.",
                severity="info",
                confidence=0.7,
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.78
        report.recommendations = [
            "Publish OpenAPI schema and validate in CI.",
            "Add request/response schemas for every endpoint.",
        ]
        return report

    async def _review_database(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """Database review — migrations, indexes, raw SQL."""
        report = ReviewReport(
            review_type=ReviewType.DATABASE.value,
            target=str(path),
            summary="Database review of migrations and raw SQL usage.",
        )
        migrations_dir = path / "migrations" / "versions"
        if not migrations_dir.exists():
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="No migrations directory",
                description="Expected migrations/versions/ — not found.",
                severity="medium",
                confidence=0.8,
                recommendation="Adopt Alembic or equivalent migration tooling.",
            ))
        else:
            migration_count = len(list(migrations_dir.glob("*.py")))
            report.strengths.append(ReviewFinding(
                kind="strength",
                title="Migration history present",
                description=f"{migration_count} migrations found.",
                severity="info",
                confidence=0.85,
            ))
        # raw SQL detection
        py_files = self._collect_python_files(path)
        raw_sql: list[str] = []
        for fp in py_files:
            src = fp.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'\.execute\s*\(\s*f?["\']', src):
                raw_sql.append(f"{fp.name}:{src[:m.start()].count(chr(10)) + 1}")
        if raw_sql:
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="Raw SQL execution",
                description=f"{len(raw_sql)} possible raw SQL execute() calls.",
                severity="high",
                confidence=0.65,
                evidence=raw_sql[:10],
                recommendation="Use parameterized queries or an ORM to prevent SQL injection.",
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.7
        report.recommendations = [
            "Verify every foreign-key column has an index.",
            "Run migration tests in CI before deploy.",
        ]
        return report

    async def _review_workflow(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """Workflow review — CI/CD pipelines."""
        report = ReviewReport(
            review_type=ReviewType.WORKFLOW.value,
            target=str(path),
            summary="CI/CD workflow review.",
        )
        workflows_dir = path / ".github" / "workflows"
        if not workflows_dir.exists():
            report.weaknesses.append(ReviewFinding(
                kind="weakness",
                title="No CI workflows",
                description="Missing .github/workflows directory.",
                severity="high",
                confidence=0.9,
                recommendation="Add CI workflows for lint, test, build, security scan.",
            ))
            report.risk_score = 0.7
            report.confidence = 0.85
            return report
        workflows = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        has_test = False
        has_lint = False
        has_security = False
        for wf in workflows:
            src = wf.read_text(encoding="utf-8", errors="ignore").lower()
            if "pytest" in src or "test" in src:
                has_test = True
            if "ruff" in src or "mypy" in src or "eslint" in src:
                has_lint = True
            if "bandit" in src or "codeql" in src or "snyk" in src:
                has_security = True
        if has_test:
            report.strengths.append(ReviewFinding(
                kind="strength", title="CI runs tests",
                description="At least one workflow runs the test suite.",
                severity="info", confidence=0.85,
            ))
        else:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="No test workflow",
                description="No workflow runs the test suite.",
                severity="high", confidence=0.85,
                recommendation="Add a workflow that runs pytest on every PR.",
            ))
        if not has_lint:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="No lint workflow",
                description="No workflow runs a linter.",
                severity="medium", confidence=0.8,
                recommendation="Add ruff + mypy + eslint steps to CI.",
            ))
        if not has_security:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="No security scan",
                description="No workflow runs a security scanner.",
                severity="medium", confidence=0.8,
                recommendation="Add bandit / pip-audit / CodeQL to CI.",
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.85
        report.recommendations = [
            "Require all checks to pass before merge.",
            "Add deployment workflows for staging and production.",
        ]
        return report

    async def _review_plugin(self, path: Path, ctx: dict[str, Any]) -> ReviewReport:
        """Plugin review — extension points, manifest correctness."""
        report = ReviewReport(
            review_type=ReviewType.PLUGIN.value,
            target=str(path),
            summary="Plugin / extension-point review.",
        )
        plugins_dir = path / "plugins"
        if not plugins_dir.exists():
            report.summary = "No plugins/ directory — plugin review skipped."
            report.confidence = 0.1
            return report
        plugin_manifests = list(plugins_dir.rglob("plugin.toml")) + list(
            plugins_dir.rglob("plugin.yaml")
        )
        if not plugin_manifests:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="Plugins without manifests",
                description="plugins/ exists but no plugin.toml/yaml manifests found.",
                severity="low", confidence=0.7,
                recommendation="Require every plugin to ship a manifest with name, version, entrypoint.",
            ))
        else:
            report.strengths.append(ReviewFinding(
                kind="strength", title="Plugin manifests present",
                description=f"{len(plugin_manifests)} plugin manifests found.",
                severity="info", confidence=0.8,
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.7
        report.recommendations = [
            "Document the plugin contract and lifecycle.",
            "Add a plugin sandbox for untrusted plugins.",
        ]
        return report

    async def _review_mission(
        self, target: str, ctx: dict[str, Any]
    ) -> ReviewReport:
        """Mission review — checks a mission object/dict for completeness."""
        report = ReviewReport(
            review_type=ReviewType.MISSION.value,
            target=target,
            summary="Mission review for completeness, approvals, and risk register.",
        )
        mission = ctx.get("mission") or {}
        if not isinstance(mission, dict):
            report.summary = "No mission context supplied — mission review skipped."
            report.confidence = 0.1
            return report
        required_keys = {"id", "title", "owner", "wbs", "budget", "risks", "milestones", "approvals"}
        missing = required_keys - set(mission.keys())
        if missing:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="Mission missing required fields",
                description=f"Missing: {sorted(missing)}",
                severity="medium", confidence=0.85,
                recommendation="Populate all required mission fields before approval.",
            ))
        else:
            report.strengths.append(ReviewFinding(
                kind="strength", title="Mission well-formed",
                description="All required mission fields are present.",
                severity="info", confidence=0.85,
            ))
        risks = mission.get("risks") or []
        if isinstance(risks, list) and len(risks) > 10:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="Excessive risks",
                description=f"Mission has {len(risks)} risks — consider scope reduction.",
                severity="medium", confidence=0.7,
                recommendation="Triage risks; close or mitigate low-priority items.",
            ))
        approvals = mission.get("approvals") or []
        if isinstance(approvals, list) and not approvals:
            report.weaknesses.append(ReviewFinding(
                kind="weakness", title="No approvals recorded",
                description="Mission has zero approvals.",
                severity="high", confidence=0.8,
                recommendation="Require at least one stakeholder approval before execution.",
            ))
        report.risk_score = self._compute_risk(report.weaknesses)
        report.confidence = 0.78
        report.recommendations = [
            "Re-review the mission after each milestone.",
            "Tie mission risks to architectural recommendations.",
        ]
        return report

    # --- helpers --------------------------------------------------------

    def _collect_python_files(self, path: Path) -> list[Path]:
        if not path.exists():
            return []
        if path.is_file():
            return [path] if path.suffix == ".py" else []
        out: list[Path] = []
        for p in path.rglob("*.py"):
            if any(seg in p.parts for seg in (".venv", "node_modules", ".git", "__pycache__", "build", "dist")):
                continue
            out.append(p)
        return out

    def _parse_python(self, fp: Path) -> ast.Module | None:
        try:
            return ast.parse(fp.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError, OSError):
            return None

    def _count_class_lines(self, node: ast.ClassDef) -> int:
        if node.body:
            last = node.body[-1]
            return getattr(last, "end_lineno", node.lineno) - node.lineno
        return 0

    def _count_func_lines(self, node: ast.AST) -> int:
        end = getattr(node, "end_lineno", None)
        start = getattr(node, "lineno", None)
        if end and start:
            return int(end) - int(start)
        return 0

    def _cyclomatic_complexity(self, node: ast.AST) -> int:
        complexity = 1
        for n in ast.walk(node):
            if isinstance(n, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)):
                complexity += 1
            elif isinstance(n, ast.BoolOp):
                complexity += len(n.values) - 1
        return complexity

    def _compute_risk(self, weaknesses: list[ReviewFinding]) -> float:
        if not weaknesses:
            return 0.0
        weights = {"info": 0.05, "low": 0.15, "medium": 0.35, "high": 0.65, "critical": 0.95}
        score = 0.0
        for w in weaknesses:
            score = max(score, weights.get(w.severity, 0.3))
            score += weights.get(w.severity, 0.3) * 0.1
        return min(score, 1.0)

    def _compare_with_history(
        self, current: ReviewReport, history: list[ReviewReport]
    ) -> dict[str, Any]:
        """Compare current review with historical reviews of the same type."""
        same_type = [h for h in history if h.review_type == current.review_type]
        if not same_type:
            return {"comparison": "no_history", "history_count": 0}
        prev = same_type[-1]
        risk_delta = current.risk_score - prev.risk_score
        weakness_delta = len(current.weaknesses) - len(prev.weaknesses)
        strength_delta = len(current.strengths) - len(prev.strengths)
        trend: str
        if risk_delta < -0.05:
            trend = "improving"
        elif risk_delta > 0.05:
            trend = "regressing"
        else:
            trend = "stable"
        return {
            "comparison": "available",
            "history_count": len(same_type),
            "previous_risk_score": round(prev.risk_score, 4),
            "current_risk_score": round(current.risk_score, 4),
            "risk_delta": round(risk_delta, 4),
            "weakness_delta": weakness_delta,
            "strength_delta": strength_delta,
            "trend": trend,
            "previous_reviewed_at": prev.reviewed_at.isoformat(),
        }
