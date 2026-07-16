"""Phase 18 — Test Intelligence Engine.

Analyzes existing tests (unit / integration / e2e / performance / stress /
security / mutation readiness), computes coverage trends, identifies flaky,
long-running, missing, and duplicate tests, and generates test-case
recommendations.

CRITICAL: This engine NEVER generates production code automatically. It only
*recommends* test cases; the engineer decides whether to write them.
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
    "TestCaseInfo",
    "TestCoverageReport",
    "TestIntelligenceEngine",
    "TestRiskReport",
    "TestSuiteAnalysis",
    "TestType",
]


class TestType(StrEnum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    STRESS = "stress"
    SECURITY = "security"
    MUTATION = "mutation"


@dataclass
class TestCaseInfo:
    """A single test case as understood by the engine."""

    test_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    file: str = ""
    line: int = 0
    test_type: str = TestType.UNIT.value
    markers: list[str] = field(default_factory=list)
    estimated_duration_ms: float = 0.0
    has_fixtures: bool = False
    has_assertions: bool = False
    is_async: bool = False
    is_parametrized: bool = False
    flaky_risk_score: float = 0.0  # 0..1

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "test_type": self.test_type,
            "markers": list(self.markers),
            "estimated_duration_ms": round(self.estimated_duration_ms, 2),
            "has_fixtures": self.has_fixtures,
            "has_assertions": self.has_assertions,
            "is_async": self.is_async,
            "is_parametrized": self.is_parametrized,
            "flaky_risk_score": round(self.flaky_risk_score, 4),
        }


@dataclass
class TestSuiteAnalysis:
    """Aggregated analysis of a test suite."""

    analysis_id: str = field(default_factory=lambda: uuid4().hex[:12])
    total_tests: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_fixtures: int = 0
    unused_fixtures: list[str] = field(default_factory=list)
    duplicate_tests: list[dict[str, Any]] = field(default_factory=list)
    long_running_tests: list[TestCaseInfo] = field(default_factory=list)
    flaky_candidates: list[TestCaseInfo] = field(default_factory=list)
    missing_tests: list[dict[str, Any]] = field(default_factory=list)
    mutation_readiness: float = 0.0
    coverage_trend: list[dict[str, Any]] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "total_tests": self.total_tests,
            "by_type": dict(self.by_type),
            "total_files": self.total_files,
            "total_fixtures": self.total_fixtures,
            "unused_fixtures": list(self.unused_fixtures),
            "duplicate_tests": list(self.duplicate_tests),
            "long_running_tests": [t.to_dict() for t in self.long_running_tests],
            "flaky_candidates": [t.to_dict() for t in self.flaky_candidates],
            "missing_tests": list(self.missing_tests),
            "mutation_readiness": round(self.mutation_readiness, 4),
            "coverage_trend": list(self.coverage_trend),
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class TestCoverageReport:
    """Coverage report — file-level + suite-level."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    overall_pct: float = 0.0
    by_directory: dict[str, float] = field(default_factory=dict)
    by_test_type: dict[str, float] = field(default_factory=dict)
    uncovered_files: list[str] = field(default_factory=list)
    undercovered_files: list[dict[str, Any]] = field(default_factory=list)
    heat_map: list[dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "overall_pct": round(self.overall_pct, 2),
            "by_directory": dict(self.by_directory),
            "by_test_type": dict(self.by_test_type),
            "uncovered_files": list(self.uncovered_files),
            "undercovered_files": list(self.undercovered_files),
            "heat_map": list(self.heat_map),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class TestRiskReport:
    """Risk-focused test report (regression risk + recommendations)."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    regression_risk_score: float = 0.0
    risk_factors: list[str] = field(default_factory=list)
    recommended_test_cases: list[dict[str, Any]] = field(default_factory=list)
    regression_predictions: list[dict[str, Any]] = field(default_factory=list)
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    requires_approval: bool = True
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "regression_risk_score": round(self.regression_risk_score, 4),
            "risk_factors": list(self.risk_factors),
            "recommended_test_cases": list(self.recommended_test_cases),
            "regression_predictions": list(self.regression_predictions),
            "execution_history": list(self.execution_history),
            "confidence": round(self.confidence, 4),
            "requires_approval": self.requires_approval,
            "generated_at": self.generated_at.isoformat(),
        }


class TestIntelligenceEngine:
    """Phase 18 — Test Intelligence.

    Analyzes tests, computes coverage/risk, and recommends test cases.
    Never generates production code.
    """

    # --- public API -----------------------------------------------------

    async def analyze_suite(self, root: str | Path) -> TestSuiteAnalysis:
        """Analyze the test suite at ``root`` (typically the tests/ dir)."""
        root_path = Path(root)
        analysis = TestSuiteAnalysis()
        if not root_path.exists():
            return analysis
        test_files = sorted(root_path.rglob("test_*.py"))
        analysis.total_files = len(test_files)
        all_tests: list[TestCaseInfo] = []
        fixture_definitions: dict[str, str] = {}  # name → file
        fixture_usages: dict[str, int] = {}

        for tf in test_files:
            try:
                tree = ast.parse(tf.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            src_lines = tf.read_text(encoding="utf-8", errors="ignore").splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        ti = self._build_test_info(node, tf, src_lines)
                        all_tests.append(ti)
                        analysis.by_type[ti.test_type] = analysis.by_type.get(ti.test_type, 0) + 1
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Name) and dec.id == "fixture":
                            fixture_definitions[node.name] = str(tf.relative_to(root_path))
                # detect fixture usage
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    fname = node.func.id
                    if fname not in fixture_usages:
                        fixture_usages[fname] = 0
                    fixture_usages[fname] += 1

        analysis.total_tests = len(all_tests)
        analysis.total_fixtures = len(fixture_definitions)
        # unused fixtures: defined but never referenced outside the definition file
        for fname, fpath in fixture_definitions.items():
            # A fixture is typically referenced as a parameter, not a call.
            # We approximate "unused" by absence of the name in the source text.
            text_used = sum(
                1 for tf in test_files if fname in tf.read_text(encoding="utf-8", errors="ignore")
            )
            if text_used <= 1:  # only the definition file mentions it
                analysis.unused_fixtures.append(f"{fname} ({fpath})")

        # duplicate detection by (name, line-count) signature
        sig_map: dict[str, list[TestCaseInfo]] = {}
        for t in all_tests:
            sig = t.name
            sig_map.setdefault(sig, []).append(t)
        for sig, group in sig_map.items():
            if len(group) > 1:
                analysis.duplicate_tests.append({
                    "signature": sig,
                    "occurrences": [
                        {"file": t.file, "line": t.line} for t in group
                    ],
                })

        # long-running tests (heuristic: sleeps, time.sleep, asyncio.sleep, network)
        for t in all_tests:
            if t.estimated_duration_ms > 500:
                analysis.long_running_tests.append(t)

        # flaky candidates (heuristic: random, datetime.now, time.time, network)
        for t in all_tests:
            if t.flaky_risk_score > 0.5:
                analysis.flaky_candidates.append(t)

        # missing tests: source files without corresponding test files
        analysis.missing_tests = await self._find_missing_tests(root_path)

        # mutation readiness: rough score
        has_assertions = sum(1 for t in all_tests if t.has_assertions)
        analysis.mutation_readiness = (
            has_assertions / max(1, len(all_tests))
        )
        return analysis

    async def coverage_report(
        self,
        root: str | Path,
        *,
        coverage_xml: str | Path | None = None,
    ) -> TestCoverageReport:
        """Generate a coverage report. Uses coverage XML if available."""
        report = TestCoverageReport()
        root_path = Path(root)
        # Try to read coverage.xml
        cov_path = Path(coverage_xml) if coverage_xml else root_path / "coverage" / "coverage.xml"
        if cov_path.exists():
            try:
                import defusedxml.ElementTree as DefusedET
                tree = DefusedET.parse(cov_path)
                root_el = tree.getroot()
                if root_el is None:
                    raise ValueError("coverage XML has no root element")
                # <coverage line-rate="0.42" ...>
                line_rate = float(root_el.attrib.get("line-rate", "0"))
                report.overall_pct = line_rate * 100.0
                # per-file
                by_dir: dict[str, list[float]] = {}
                for cls in root_el.iter("class"):
                    fname = cls.attrib.get("filename", "")
                    lr = float(cls.attrib.get("line-rate", "0")) * 100.0
                    parent = str(Path(fname).parent) or "."
                    by_dir.setdefault(parent, []).append(lr)
                    if lr < 1.0 and lr > 0:
                        report.undercovered_files.append({
                            "file": fname, "coverage_pct": round(lr, 1),
                        })
                    elif lr == 0:
                        report.uncovered_files.append(fname)
                for d, vals in by_dir.items():
                    report.by_directory[d] = round(sum(vals) / len(vals), 2)
                # heat map: top-N undercovered files
                report.heat_map = sorted(
                    report.undercovered_files,
                    key=lambda x: x["coverage_pct"],
                )[:20]
            except (DefusedET.ParseError, OSError, ValueError):
                _log.warning("test_intel.coverage_xml_unparseable", path=str(cov_path))

        # by_test_type: count tests by type
        analysis = await self.analyze_suite(root_path / "tests" if (root_path / "tests").exists() else root_path)
        total = max(1, analysis.total_tests)
        report.by_test_type = {
            t: round(c / total * 100, 2) for t, c in analysis.by_type.items()
        }
        return report

    async def risk_report(
        self,
        root: str | Path,
        *,
        recent_failures: list[dict[str, Any]] | None = None,
    ) -> TestRiskReport:
        """Generate a risk report with recommended test cases and predictions."""
        report = TestRiskReport()
        analysis = await self.analyze_suite(root)
        risk_factors: list[str] = []
        if analysis.total_tests < 50:
            risk_factors.append("low_test_count")
            report.regression_risk_score += 0.2
        if len(analysis.unused_fixtures) > 5:
            risk_factors.append("excessive_unused_fixtures")
            report.regression_risk_score += 0.05
        if analysis.long_running_tests:
            risk_factors.append("long_running_tests_present")
            report.regression_risk_score += 0.05
        if analysis.flaky_candidates:
            risk_factors.append("flaky_candidates_present")
            report.regression_risk_score += 0.1
        if len(analysis.missing_tests) > 10:
            risk_factors.append("many_missing_tests")
            report.regression_risk_score += 0.15
        if analysis.mutation_readiness < 0.5:
            risk_factors.append("low_mutation_readiness")
            report.regression_risk_score += 0.1
        if recent_failures:
            failure_rate = len(recent_failures) / max(1, analysis.total_tests)
            if failure_rate > 0.05:
                risk_factors.append("high_recent_failure_rate")
                report.regression_risk_score += 0.2
            report.execution_history = recent_failures[-20:]
        report.regression_risk_score = min(report.regression_risk_score, 1.0)
        report.risk_factors = risk_factors
        # recommended test cases (engineer writes them; we never generate code)
        for missing in analysis.missing_tests[:10]:
            report.recommended_test_cases.append({
                "type": "missing_test",
                "target": missing.get("source_file"),
                "suggested_name": f"test_{Path(missing.get('source_file', 'x')).stem}_basic",
                "reason": "No test file found for this source file.",
                "confidence": 0.7,
                "requires_approval": True,
            })
        for t in analysis.long_running_tests[:5]:
            report.recommended_test_cases.append({
                "type": "split_long_test",
                "target": f"{t.file}::{t.name}",
                "suggested_name": f"{t.name}_fast_variant",
                "reason": f"Test estimated >500ms ({t.estimated_duration_ms:.0f}ms).",
                "confidence": 0.6,
                "requires_approval": True,
            })
        for t in analysis.flaky_candidates[:5]:
            report.recommended_test_cases.append({
                "type": "stabilize_flaky",
                "target": f"{t.file}::{t.name}",
                "suggested_name": f"{t.name}_deterministic",
                "reason": "Test uses non-deterministic constructs (random/time/network).",
                "confidence": 0.65,
                "requires_approval": True,
            })
        # regression predictions
        report.regression_predictions = [
            {
                "module": "high_complexity_areas",
                "prediction": "Likely to regress if test count does not grow with source.",
                "confidence": 0.6,
                "evidence": [f"missing_tests={len(analysis.missing_tests)}"],
            },
            {
                "module": "flaky_tests",
                "prediction": "Will intermittently fail until stabilized.",
                "confidence": 0.7,
                "evidence": [f"flaky_candidates={len(analysis.flaky_candidates)}"],
            },
        ]
        report.confidence = 0.7
        return report

    # --- helpers --------------------------------------------------------

    def _build_test_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        tf: Path,
        src_lines: list[str],
    ) -> TestCaseInfo:
        markers: list[str] = []
        has_fixtures = bool(node.args.args)
        is_async = isinstance(node, ast.AsyncFunctionDef)
        is_parametrized = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Attribute):
                if dec.value.attr == "mark":
                    markers.append(dec.attr)
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr == "parametrize":
                    is_parametrized = True
            if isinstance(dec, ast.Attribute) and dec.attr == "slow":
                markers.append("slow")
        # rough duration estimate from sleeps and asserts in body
        duration = 0.0
        has_assertions = False
        flaky_signals = 0
        body_text = "\n".join(src_lines[node.lineno - 1: getattr(node, "end_lineno", node.lineno)])
        for m in re.finditer(r"asyncio\.sleep\((\d+(?:\.\d+)?)\)", body_text):
            duration += float(m.group(1)) * 1000
        for m in re.finditer(r"time\.sleep\((\d+(?:\.\d+)?)\)", body_text):
            duration += float(m.group(1)) * 1000
        if "assert" in body_text:
            has_assertions = True
        # flaky signals
        if re.search(r"\brandom\b", body_text):
            flaky_signals += 1
        if re.search(r"\bdatetime\.now\b", body_text):
            flaky_signals += 1
        if re.search(r"\btime\.time\(\)", body_text):
            flaky_signals += 1
        if re.search(r"\bsocket\b|\bhttpx\b|\brequests\b", body_text) and "mock" not in body_text.lower():
            flaky_signals += 1
        flaky_risk = min(flaky_signals * 0.25, 1.0)
        # test type inference
        test_type = TestType.UNIT.value
        rel_path = str(tf).lower()
        if "integration" in rel_path:
            test_type = TestType.INTEGRATION.value
        elif "e2e" in rel_path:
            test_type = TestType.E2E.value
        elif "performance" in rel_path:
            test_type = TestType.PERFORMANCE.value
        elif "stress" in rel_path:
            test_type = TestType.STRESS.value
        elif "security" in rel_path:
            test_type = TestType.SECURITY.value
        elif "slow" in markers:
            test_type = TestType.PERFORMANCE.value

        return TestCaseInfo(
            name=node.name,
            file=str(tf),
            line=node.lineno,
            test_type=test_type,
            markers=markers,
            estimated_duration_ms=duration,
            has_fixtures=has_fixtures,
            has_assertions=has_assertions,
            is_async=is_async,
            is_parametrized=is_parametrized,
            flaky_risk_score=flaky_risk,
        )

    async def _find_missing_tests(self, tests_root: Path) -> list[dict[str, Any]]:
        """Find source files without a corresponding test file."""
        # Walk up to find the project root (parent of tests/)
        project_root = tests_root.parent
        source_files: list[Path] = []
        for p in project_root.rglob("*.py"):
            if "tests" in p.parts or any(
                seg in p.parts for seg in (".venv", "node_modules", ".git", "__pycache__", "build", "dist")
            ):
                continue
            source_files.append(p)
        test_names = {p.stem for p in tests_root.rglob("test_*.py")}
        # Map source file foo.py → expect test_foo.py
        missing: list[dict[str, Any]] = []
        for sf in source_files:
            expected_test = f"test_{sf.stem}"
            if expected_test not in test_names and not sf.name.startswith("__"):
                missing.append({
                    "source_file": str(sf.relative_to(project_root)),
                    "expected_test": f"{expected_test}.py",
                    "confidence": 0.75,
                })
        return missing[:50]
