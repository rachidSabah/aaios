"""Engineering Planning, Metrics, Impact Analysis, Risk, and Recommendations.

Phases 9-16: Planning Engine, Metrics Engine, Architecture Analysis,
Impact Analysis, Knowledge Integration, Recommendation Engine, Risk Engine.

All recommendations include: confidence, reasoning, evidence, risk, impact,
estimated effort, rollback strategy, and require human approval.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "ArchAnalysisResult",
    "EngPlan",
    "EngPlanItem",
    "EngRecommendation",
    "EngRiskAssessment",
    "EngineeringMetrics",
    "ImpactResult",
    "MetricsEngine",
    "PlanningEngine",
    "RiskEngine",
]


@dataclass
class EngPlanItem:
    """A single item in an engineering plan."""

    item_id: str = field(default_factory=lambda: uuid4().hex[:8])
    title: str = ""
    description: str = ""
    item_type: str = "task"  # epic, feature, task, subtask
    priority: str = "normal"
    estimated_hours: float = 0.0
    complexity: str = "medium"  # low, medium, high
    dependencies: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "description": self.description,
            "item_type": self.item_type,
            "priority": self.priority,
            "estimated_hours": round(self.estimated_hours, 2),
            "complexity": self.complexity,
            "dependencies": list(self.dependencies),
            "risks": list(self.risks),
            "confidence": round(self.confidence, 4),
        }


@dataclass
class EngPlan:
    """An engineering plan with WBS, timeline, and risk assessment."""

    plan_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    items: list[EngPlanItem] = field(default_factory=list)
    total_estimated_hours: float = 0.0
    confidence: float = 0.5
    reasoning: str = ""
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    requires_approval: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "items": [i.to_dict() for i in self.items],
            "total_estimated_hours": round(self.total_estimated_hours, 2),
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "assumptions": list(self.assumptions),
            "constraints": list(self.constraints),
            "risks": list(self.risks),
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EngineeringMetrics:
    """Engineering quality metrics for a repository."""

    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    avg_cyclomatic_complexity: float = 0.0
    avg_cognitive_complexity: float = 0.0
    avg_maintainability_index: float = 0.0
    technical_debt_hours: float = 0.0
    code_duplication_pct: float = 0.0
    test_coverage_pct: float = 0.0
    documentation_coverage_pct: float = 0.0
    comment_density: float = 0.0
    dependency_count: int = 0
    architecture_violations: int = 0
    dead_code_count: int = 0
    unused_imports: int = 0
    risk_score: float = 0.0
    engineering_maturity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "avg_cyclomatic_complexity": round(self.avg_cyclomatic_complexity, 4),
            "avg_cognitive_complexity": round(self.avg_cognitive_complexity, 4),
            "avg_maintainability_index": round(self.avg_maintainability_index, 4),
            "technical_debt_hours": round(self.technical_debt_hours, 2),
            "code_duplication_pct": round(self.code_duplication_pct, 2),
            "test_coverage_pct": round(self.test_coverage_pct, 2),
            "documentation_coverage_pct": round(self.documentation_coverage_pct, 2),
            "comment_density": round(self.comment_density, 4),
            "dependency_count": self.dependency_count,
            "architecture_violations": self.architecture_violations,
            "dead_code_count": self.dead_code_count,
            "unused_imports": self.unused_imports,
            "risk_score": round(self.risk_score, 4),
            "engineering_maturity": round(self.engineering_maturity, 4),
        }


@dataclass
class ArchAnalysisResult:
    """Architecture analysis result."""

    violations: list[dict[str, Any]] = field(default_factory=list)
    god_classes: list[str] = field(default_factory=list)
    circular_refs: list[dict[str, str]] = field(default_factory=list)
    layer_violations: list[dict[str, Any]] = field(default_factory=list)
    boundary_violations: list[dict[str, Any]] = field(default_factory=list)
    over_engineering: list[str] = field(default_factory=list)
    under_engineering: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "violations": list(self.violations),
            "god_classes": list(self.god_classes),
            "circular_refs": list(self.circular_refs),
            "layer_violations": list(self.layer_violations),
            "boundary_violations": list(self.boundary_violations),
            "over_engineering": list(self.over_engineering),
            "under_engineering": list(self.under_engineering),
            "recommendations": list(self.recommendations),
        }


@dataclass
class ImpactResult:
    """Impact analysis result."""

    affected_modules: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    affected_apis: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    affected_docs: list[str] = field(default_factory=list)
    affected_workflows: list[str] = field(default_factory=list)
    risk: str = "medium"
    complexity: str = "medium"
    testing_effort_hours: float = 0.0
    migration_effort_hours: float = 0.0
    rollback_effort_hours: float = 0.0
    confidence: float = 0.5
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "affected_modules": list(self.affected_modules),
            "affected_services": list(self.affected_services),
            "affected_apis": list(self.affected_apis),
            "affected_tests": list(self.affected_tests),
            "affected_docs": list(self.affected_docs),
            "affected_workflows": list(self.affected_workflows),
            "risk": self.risk,
            "complexity": self.complexity,
            "testing_effort_hours": round(self.testing_effort_hours, 2),
            "migration_effort_hours": round(self.migration_effort_hours, 2),
            "rollback_effort_hours": round(self.rollback_effort_hours, 2),
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
        }


@dataclass
class EngRecommendation:
    """An engineering recommendation (never auto-applied)."""

    recommendation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    category: str = ""  # architecture, performance, security, etc.
    priority: str = "normal"
    severity: str = "medium"
    confidence: float = 0.5
    evidence: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    historical_references: list[str] = field(default_factory=list)
    risk: str = "medium"
    impact: float = 0.5
    estimated_effort_hours: float = 0.0
    rollback_strategy: str = ""
    requires_approval: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "severity": self.severity,
            "confidence": round(self.confidence, 4),
            "evidence": dict(self.evidence),
            "reasoning": self.reasoning,
            "historical_references": list(self.historical_references),
            "risk": self.risk,
            "impact": round(self.impact, 4),
            "estimated_effort_hours": round(self.estimated_effort_hours, 2),
            "rollback_strategy": self.rollback_strategy,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class EngRiskAssessment:
    """Engineering risk assessment."""

    risk_id: str = field(default_factory=lambda: uuid4().hex[:12])
    risk_type: str = ""  # regression, performance, security, compatibility, etc.
    description: str = ""
    risk_score: float = 0.0
    confidence: float = 0.5
    mitigation_strategy: str = ""
    alternative_approaches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "risk_type": self.risk_type,
            "description": self.description,
            "risk_score": round(self.risk_score, 4),
            "confidence": round(self.confidence, 4),
            "mitigation_strategy": self.mitigation_strategy,
            "alternative_approaches": list(self.alternative_approaches),
        }


class PlanningEngine:
    """Engineering Planning Engine — decomposes requirements into WBS.

    Phase 9: Planning Engine.
    """

    async def create_plan(
        self,
        title: str,
        description: str,
        requirements: list[str],
        *,
        max_hours: float = 100.0,
    ) -> EngPlan:
        """Create an engineering plan from requirements."""
        plan = EngPlan(title=title, description=description)
        total_hours = 0.0
        for req in requirements:
            item = EngPlanItem(
                title=req[:80],
                description=req,
                item_type="task",
                estimated_hours=min(8.0, max(1.0, len(req) / 10)),
                complexity="medium" if len(req) > 50 else "low",
                confidence=0.7,
            )
            plan.items.append(item)
            total_hours += item.estimated_hours
        plan.total_estimated_hours = total_hours
        plan.confidence = 0.6 if total_hours < max_hours else 0.4
        plan.reasoning = (
            f"Plan decomposed {len(requirements)} requirements into {len(plan.items)} tasks."
        )
        plan.assumptions = [
            "Requirements are complete and unambiguous",
            "Team has necessary skills and tools",
            "No external blockers",
        ]
        plan.constraints = [
            f"Maximum effort: {max_hours} hours",
            "All changes require human approval",
        ]
        plan.risks = [
            "Requirements may change during implementation",
            "Dependencies may introduce delays",
        ]
        return plan

    async def critical_path(self, plan: EngPlan) -> list[str]:
        """Calculate the critical path through the plan."""
        # Simple: return items in dependency order
        ordered: list[str] = []
        remaining = {i.item_id: i for i in plan.items}
        while remaining:
            ready = [
                iid
                for iid, item in remaining.items()
                if all(d in ordered for d in item.dependencies)
            ]
            if not ready:
                # No ready items — just take the first remaining
                ready = list(remaining.keys())[:1]
            for iid in ready[:1]:
                ordered.append(iid)
                del remaining[iid]
        return ordered


class MetricsEngine:
    """Computes engineering quality metrics.

    Phase 11: Engineering Metrics Engine.
    """

    async def compute_metrics(self, repo_root: Path) -> EngineeringMetrics:
        """Compute comprehensive engineering metrics."""
        metrics = EngineeringMetrics()
        complexities: list[float] = []
        comment_count = 0
        code_count = 0
        skip_dirs = {
            ".git",
            ".venv",
            "node_modules",
            "__pycache__",
            ".mypy_cache",
            "dist",
            "build",
            ".next",
        }

        for py_file in repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                lines = source.splitlines()
                metrics.total_files += 1
                metrics.total_lines += len(lines)
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        metrics.total_classes += 1
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        metrics.total_functions += 1
                        # Cyclomatic complexity (simplified)
                        branches = sum(
                            1
                            for n in ast.walk(node)
                            if isinstance(
                                n, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.BoolOp)
                            )
                        )
                        complexities.append(max(1, branches))
                # Comment density
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        comment_count += 1
                    elif stripped:
                        code_count += 1
            except Exception:
                pass

        metrics.avg_cyclomatic_complexity = sum(complexities) / max(1, len(complexities))
        metrics.avg_cognitive_complexity = metrics.avg_cyclomatic_complexity * 1.2  # approximation
        # Maintainability Index (simplified)
        if metrics.total_lines > 0:
            mi = max(
                0.0,
                min(
                    100.0,
                    171
                    - 5.2 * (metrics.total_lines / max(1, metrics.total_functions))
                    - 0.37 * metrics.avg_cyclomatic_complexity,
                ),
            )
            metrics.avg_maintainability_index = mi / 100.0
        metrics.comment_density = comment_count / max(1, code_count)
        # Test coverage estimation
        test_dir = repo_root / "tests"
        if test_dir.exists() and metrics.total_files > 0:
            test_files = len(list(test_dir.rglob("*.py")))
            metrics.test_coverage_pct = min(100.0, (test_files / max(1, metrics.total_files)) * 100)
        # Documentation coverage
        doc_count = 0
        total_classes_funcs = metrics.total_classes + metrics.total_functions
        if total_classes_funcs > 0:
            for py_file in repo_root.rglob("*.py"):
                if any(skip in str(py_file) for skip in skip_dirs):
                    continue
                try:
                    tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                            if ast.get_docstring(node):
                                doc_count += 1
                except Exception:
                    pass
            metrics.documentation_coverage_pct = (doc_count / total_classes_funcs) * 100
        # Technical debt (simplified: based on complexity and missing docs)
        metrics.technical_debt_hours = (
            metrics.avg_cyclomatic_complexity * 0.5
            + (100 - metrics.documentation_coverage_pct) * 0.1
            + (100 - metrics.test_coverage_pct) * 0.1
        ) * max(1, metrics.total_files / 100)
        # Risk score
        metrics.risk_score = min(
            1.0,
            metrics.avg_cyclomatic_complexity / 20.0 + (100 - metrics.test_coverage_pct) / 200.0,
        )
        # Engineering maturity
        maturity = 0.0
        if metrics.test_coverage_pct > 50:
            maturity += 0.2
        if metrics.documentation_coverage_pct > 50:
            maturity += 0.2
        if metrics.avg_maintainability_index > 0.5:
            maturity += 0.2
        if metrics.avg_cyclomatic_complexity < 10:
            maturity += 0.2
        if metrics.technical_debt_hours < 100:
            maturity += 0.2
        metrics.engineering_maturity = maturity
        return metrics


class ArchitectureAnalysisEngine:
    """Deep architecture analysis.

    Phase 12: Architecture Analysis Engine.
    """

    async def analyze(self, repo_root: Path) -> ArchAnalysisResult:
        """Analyze architecture for violations and issues."""
        result = ArchAnalysisResult()
        skip_dirs = {".git", ".venv", "node_modules", "__pycache__"}

        # Detect god classes (classes with > 50 methods/attributes)
        for py_file in repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        members = sum(
                            1
                            for n in node.body
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign))
                        )
                        if members > 30:
                            result.god_classes.append(
                                f"{py_file.name}:{node.name} ({members} members)"
                            )
            except Exception:
                pass

        # Detect layer violations
        layer_map = {
            "core": 1,
            "services": 2,
            "agents": 3,
            "supervisor": 4,
            "orchestrator": 4,
            "surfaces": 5,
        }
        for src_dir, src_layer in layer_map.items():
            dir_path = repo_root / src_dir
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in skip_dirs):
                    continue
                try:
                    tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            for target_dir, target_layer in layer_map.items():
                                if target_dir == src_dir:
                                    continue
                                if node.module.startswith(target_dir) and target_layer > src_layer:
                                    result.layer_violations.append(
                                        {
                                            "file": str(py_file.relative_to(repo_root)),
                                            "import": node.module,
                                            "from_layer": f"L{src_layer}",
                                            "to_layer": f"L{target_layer}",
                                        }
                                    )
                except Exception:
                    pass

        # Recommendations
        if result.god_classes:
            result.recommendations.append(
                f"Refactor {len(result.god_classes)} god classes into smaller, focused classes"
            )
        if result.layer_violations:
            result.recommendations.append(
                f"Fix {len(result.layer_violations)} layer violations — lower layers should not import from higher layers"
            )
        if not result.recommendations:
            result.recommendations.append(
                "Architecture looks healthy — no major violations detected"
            )
        return result


class ImpactAnalysisEngine:
    """Predicts impact before implementation.

    Phase 13: Impact Analysis Engine.
    """

    async def analyze_impact(
        self,
        repo_root: Path,
        target_file: str,
        change_description: str = "",
    ) -> ImpactResult:
        """Analyze the impact of changing a file."""
        result = ImpactResult()
        target_path = Path(target_file)

        # Find files that import the target
        affected: list[str] = []
        skip_dirs = {".git", ".venv", "node_modules", "__pycache__"}
        for py_file in repo_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if target_path.stem in node.module or node.module.endswith(
                            target_path.stem
                        ):
                            affected.append(str(py_file.relative_to(repo_root)))
                            break
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if target_path.stem in alias.name:
                                affected.append(str(py_file.relative_to(repo_root)))
                                break
            except Exception:
                pass

        result.affected_modules = list(set(affected))
        # Estimate effort
        affected_count = len(result.affected_modules)
        result.testing_effort_hours = affected_count * 2.0
        result.migration_effort_hours = affected_count * 1.0
        result.rollback_effort_hours = affected_count * 0.5
        result.risk = "high" if affected_count > 10 else "medium" if affected_count > 3 else "low"
        result.complexity = (
            "high" if affected_count > 15 else "medium" if affected_count > 5 else "low"
        )
        result.confidence = 0.7 if affected_count > 0 else 0.9
        result.reasoning = (
            f"Changing {target_file} affects {affected_count} modules that import it."
        )
        return result


class RecommendationEngine:
    """Generates engineering recommendations. Never auto-applies.

    Phase 15: Engineering Recommendation Engine.
    """

    async def recommend_all(
        self, metrics: EngineeringMetrics, arch: ArchAnalysisResult
    ) -> list[EngRecommendation]:
        """Generate all applicable recommendations."""
        recs: list[EngRecommendation] = []
        # Architecture recommendations
        if arch.god_classes:
            recs.append(
                EngRecommendation(
                    title=f"Refactor {len(arch.god_classes)} god classes",
                    description="Large classes with too many responsibilities should be split.",
                    category="architecture",
                    priority="high",
                    severity="high",
                    confidence=0.8,
                    evidence={"god_classes": arch.god_classes[:5]},
                    reasoning="God classes violate single responsibility and are hard to maintain.",
                    risk="medium",
                    impact=0.7,
                    estimated_effort_hours=len(arch.god_classes) * 4.0,
                    rollback_strategy="Revert to original class structure.",
                )
            )
        if arch.layer_violations:
            recs.append(
                EngRecommendation(
                    title=f"Fix {len(arch.layer_violations)} layer violations",
                    description="Lower layers should not import from higher layers.",
                    category="architecture",
                    priority="high",
                    severity="medium",
                    confidence=0.9,
                    evidence={"violations": arch.layer_violations[:5]},
                    reasoning="Layer violations create unwanted coupling.",
                    risk="low",
                    impact=0.6,
                    estimated_effort_hours=len(arch.layer_violations) * 1.0,
                    rollback_strategy="Revert the imports.",
                )
            )
        # Performance recommendations
        if metrics.avg_cyclomatic_complexity > 10:
            recs.append(
                EngRecommendation(
                    title="Reduce cyclomatic complexity",
                    description=f"Average complexity is {metrics.avg_cyclomatic_complexity:.1f} (target: <10)",
                    category="performance",
                    priority="normal",
                    severity="medium",
                    confidence=0.7,
                    evidence={"avg_complexity": metrics.avg_cyclomatic_complexity},
                    reasoning="High complexity increases bug risk and maintenance cost.",
                    risk="low",
                    impact=0.5,
                    estimated_effort_hours=8.0,
                    rollback_strategy="Revert refactored functions.",
                )
            )
        # Testing recommendations
        if metrics.test_coverage_pct < 50:
            recs.append(
                EngRecommendation(
                    title="Improve test coverage",
                    description=f"Test coverage is {metrics.test_coverage_pct:.1f}% (target: >80%)",
                    category="testing",
                    priority="high",
                    severity="high",
                    confidence=0.9,
                    evidence={"coverage_pct": metrics.test_coverage_pct},
                    reasoning="Low test coverage increases regression risk.",
                    risk="low",
                    impact=0.8,
                    estimated_effort_hours=16.0,
                    rollback_strategy="Remove added tests if not needed.",
                )
            )
        # Documentation recommendations
        if metrics.documentation_coverage_pct < 50:
            recs.append(
                EngRecommendation(
                    title="Improve documentation coverage",
                    description=f"Documentation coverage is {metrics.documentation_coverage_pct:.1f}%",
                    category="documentation",
                    priority="normal",
                    severity="medium",
                    confidence=0.8,
                    evidence={"doc_coverage_pct": metrics.documentation_coverage_pct},
                    reasoning="Missing documentation makes onboarding harder.",
                    risk="low",
                    impact=0.4,
                    estimated_effort_hours=8.0,
                    rollback_strategy="Remove added docstrings.",
                )
            )
        # Security recommendations
        if metrics.risk_score > 0.5:
            recs.append(
                EngRecommendation(
                    title="Reduce overall risk score",
                    description=f"Risk score is {metrics.risk_score:.2f} (target: <0.5)",
                    category="security",
                    priority="high",
                    severity="high",
                    confidence=0.6,
                    evidence={"risk_score": metrics.risk_score},
                    reasoning="High risk score indicates potential security/reliability issues.",
                    risk="medium",
                    impact=0.7,
                    estimated_effort_hours=12.0,
                    rollback_strategy="Revert risk mitigation changes.",
                )
            )
        return recs


class RiskEngine:
    """Predicts engineering risks.

    Phase 16: Engineering Risk Engine.
    """

    async def assess_all(
        self, metrics: EngineeringMetrics, arch: ArchAnalysisResult
    ) -> list[EngRiskAssessment]:
        """Assess all engineering risks."""
        risks: list[EngRiskAssessment] = []
        # Regression risk
        if metrics.test_coverage_pct < 50:
            risks.append(
                EngRiskAssessment(
                    risk_type="regression",
                    description=f"Low test coverage ({metrics.test_coverage_pct:.1f}%) increases regression risk",
                    risk_score=0.7,
                    confidence=0.8,
                    mitigation_strategy="Add tests for critical paths before making changes",
                    alternative_approaches=[
                        "Increase coverage to 80%+",
                        "Add integration tests",
                        "Use mutation testing",
                    ],
                )
            )
        # Performance risk
        if metrics.avg_cyclomatic_complexity > 10:
            risks.append(
                EngRiskAssessment(
                    risk_type="performance",
                    description=f"High complexity ({metrics.avg_cyclomatic_complexity:.1f}) may indicate performance bottlenecks",
                    risk_score=0.5,
                    confidence=0.6,
                    mitigation_strategy="Profile and optimize high-complexity functions",
                    alternative_approaches=[
                        "Refactor into smaller functions",
                        "Add caching",
                        "Use async where possible",
                    ],
                )
            )
        # Compatibility risk
        if arch.layer_violations:
            risks.append(
                EngRiskAssessment(
                    risk_type="compatibility",
                    description=f"{len(arch.layer_violations)} layer violations may cause compatibility issues",
                    risk_score=0.6,
                    confidence=0.7,
                    mitigation_strategy="Fix layer violations before adding new features",
                    alternative_approaches=[
                        "Introduce interfaces",
                        "Use dependency injection",
                        "Event-driven communication",
                    ],
                )
            )
        # Maintenance risk
        if metrics.technical_debt_hours > 50:
            risks.append(
                EngRiskAssessment(
                    risk_type="maintenance",
                    description=f"Technical debt is {metrics.technical_debt_hours:.1f} hours",
                    risk_score=0.6,
                    confidence=0.7,
                    mitigation_strategy="Allocate sprint capacity to debt reduction",
                    alternative_approaches=[
                        "Refactor incrementally",
                        "Prioritize high-impact debt",
                        "Automate repetitive tasks",
                    ],
                )
            )
        # Deployment risk
        if metrics.architecture_violations > 5:
            risks.append(
                EngRiskAssessment(
                    risk_type="deployment",
                    description=f"{metrics.architecture_violations} architecture violations increase deployment risk",
                    risk_score=0.5,
                    confidence=0.6,
                    mitigation_strategy="Use feature flags for risky deployments",
                    alternative_approaches=[
                        "Canary deployments",
                        "Blue-green deployments",
                        "Gradual rollout",
                    ],
                )
            )
        return risks
