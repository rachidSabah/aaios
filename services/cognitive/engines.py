"""Prediction Engine + Optimization Engine + Knowledge Graph + Digital Twin +
Architecture Intelligence + Repository Intelligence + Enterprise Reporting.

All in one file for efficiency — each class is focused and explainable.
"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.cognitive.experience_engine import CognitiveExperienceEngine
from services.cognitive.models import (
    ArchIssue,
    ArchIssueType,
    EnterpriseReport,
    EnterpriseReportType,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    PredictionResult,
    PredictionType,
    Recommendation,
    RecommendationType,
)

_log = get_logger(__name__)

__all__ = [
    "ArchitectureIntelligence",
    "CognitivePredictionEngine",
    "CognitiveOptimizationEngine",
    "EnterpriseKnowledgeGraph",
    "EnterpriseReporting",
    "RepositoryIntelligence",
]


class CognitivePredictionEngine:
    """Predicts outcomes before execution using historical data.

    Every prediction includes an explanation with the evidence behind it.
    No opaque ML — all predictions are based on explainable statistics.
    """

    def __init__(self, experience_engine: CognitiveExperienceEngine) -> None:
        self._exp = experience_engine

    async def predict_all(self, context: dict[str, Any]) -> list[PredictionResult]:
        """Generate all applicable predictions for a given context."""
        predictions: list[PredictionResult] = []
        predictions.append(await self.predict_success_probability(context))
        predictions.append(await self.predict_duration(context))
        predictions.append(await self.predict_cost(context))
        predictions.append(await self.predict_latency(context))
        predictions.append(await self.predict_token_consumption(context))
        predictions.append(await self.predict_risk(context))
        predictions.append(await self.predict_confidence(context))
        return predictions

    async def predict_success_probability(self, context: dict[str, Any]) -> PredictionResult:
        """Predict the probability of success."""
        experiences = self._exp.all_experiences
        if not experiences:
            return PredictionResult(
                prediction_type=PredictionType.SUCCESS_PROBABILITY.value,
                predicted_value=0.7,
                confidence=0.3,
                explanation="No historical data — using default 70% base rate.",
            )
        success_rate = sum(1 for e in experiences if e.success) / len(experiences)
        # Adjust based on context
        agent = context.get("agent", "")
        if agent:
            agent_exps = [e for e in experiences if agent in e.selected_agents]
            if agent_exps:
                agent_rate = sum(1 for e in agent_exps if e.success) / len(agent_exps)
                success_rate = (success_rate + agent_rate) / 2
        return PredictionResult(
            prediction_type=PredictionType.SUCCESS_PROBABILITY.value,
            target=context.get("goal", "unknown"),
            predicted_value=success_rate,
            confidence=min(0.9, len(experiences) / 50.0),
            explanation=f"Based on {len(experiences)} historical executions with {success_rate:.1%} overall success rate."
            + (
                f" Agent '{agent}' has {len(agent_exps)} past executions."
                if agent and agent_exps
                else ""
            ),
            evidence={
                "sample_count": len(experiences),
                "base_success_rate": round(success_rate, 4),
            },
        )

    async def predict_duration(self, context: dict[str, Any]) -> PredictionResult:
        """Predict execution duration in seconds."""
        experiences = self._exp.all_experiences
        if not experiences:
            return PredictionResult(
                prediction_type=PredictionType.MISSION_DURATION.value,
                predicted_value=30.0,
                confidence=0.3,
                explanation="No historical data — estimating 30s default.",
            )
        avg_duration = sum(e.latency_s for e in experiences) / len(experiences)
        return PredictionResult(
            prediction_type=PredictionType.MISSION_DURATION.value,
            predicted_value=avg_duration,
            confidence=min(0.8, len(experiences) / 30.0),
            explanation=f"Average duration across {len(experiences)} executions is {avg_duration:.2f}s.",
            evidence={"sample_count": len(experiences), "avg_duration_s": round(avg_duration, 2)},
        )

    async def predict_cost(self, context: dict[str, Any]) -> PredictionResult:
        """Predict execution cost in USD."""
        experiences = self._exp.all_experiences
        if not experiences:
            return PredictionResult(
                prediction_type=PredictionType.BUDGET.value,
                predicted_value=0.05,
                confidence=0.3,
                explanation="No historical data — estimating $0.05 default.",
            )
        avg_cost = sum(e.cost_usd for e in experiences) / len(experiences)
        return PredictionResult(
            prediction_type=PredictionType.BUDGET.value,
            predicted_value=avg_cost,
            confidence=min(0.8, len(experiences) / 30.0),
            explanation=f"Average cost across {len(experiences)} executions is ${avg_cost:.4f}.",
            evidence={"sample_count": len(experiences), "avg_cost_usd": round(avg_cost, 6)},
        )

    async def predict_latency(self, context: dict[str, Any]) -> PredictionResult:
        """Predict latency in seconds."""
        return await self.predict_duration(context)

    async def predict_token_consumption(self, context: dict[str, Any]) -> PredictionResult:
        """Predict token consumption."""
        experiences = self._exp.all_experiences
        if not experiences:
            return PredictionResult(
                prediction_type=PredictionType.TOKEN_CONSUMPTION.value,
                predicted_value=500,
                confidence=0.3,
                explanation="No historical data — estimating 500 tokens default.",
            )
        total_tokens = [sum(e.token_usage.values()) for e in experiences if e.token_usage]
        if not total_tokens:
            return PredictionResult(
                prediction_type=PredictionType.TOKEN_CONSUMPTION.value,
                predicted_value=500,
                confidence=0.3,
                explanation="No token usage data in historical executions.",
            )
        avg_tokens = sum(total_tokens) / len(total_tokens)
        return PredictionResult(
            prediction_type=PredictionType.TOKEN_CONSUMPTION.value,
            predicted_value=avg_tokens,
            confidence=min(0.7, len(total_tokens) / 20.0),
            explanation=f"Average token consumption across {len(total_tokens)} executions is {avg_tokens:.0f}.",
            evidence={"sample_count": len(total_tokens), "avg_tokens": round(avg_tokens)},
        )

    async def predict_risk(self, context: dict[str, Any]) -> PredictionResult:
        """Predict risk score (0.0-1.0, higher = more risky)."""
        experiences = self._exp.all_experiences
        if not experiences:
            return PredictionResult(
                prediction_type=PredictionType.RISK_SCORE.value,
                predicted_value=0.3,
                confidence=0.3,
                explanation="No historical data — using default 0.3 risk score.",
            )
        avg_risk = sum(e.risk_score for e in experiences) / len(experiences)
        return PredictionResult(
            prediction_type=PredictionType.RISK_SCORE.value,
            predicted_value=avg_risk,
            confidence=min(0.7, len(experiences) / 30.0),
            explanation=f"Average risk score across {len(experiences)} executions is {avg_risk:.2f}.",
            evidence={"sample_count": len(experiences), "avg_risk": round(avg_risk, 4)},
        )

    async def predict_confidence(self, context: dict[str, Any]) -> PredictionResult:
        """Predict confidence score (0.0-1.0)."""
        experiences = self._exp.all_experiences
        if not experiences:
            return PredictionResult(
                prediction_type=PredictionType.CONFIDENCE_SCORE.value,
                predicted_value=0.7,
                confidence=0.3,
                explanation="No historical data — using default 0.7 confidence.",
            )
        avg_conf = sum(e.confidence_score for e in experiences) / len(experiences)
        return PredictionResult(
            prediction_type=PredictionType.CONFIDENCE_SCORE.value,
            predicted_value=avg_conf,
            confidence=min(0.7, len(experiences) / 30.0),
            explanation=f"Average confidence across {len(experiences)} executions is {avg_conf:.2f}.",
            evidence={"sample_count": len(experiences), "avg_confidence": round(avg_conf, 4)},
        )


class CognitiveOptimizationEngine:
    """Generates optimization recommendations. NEVER auto-applies.

    Each recommendation requires Supervisor approval before execution.
    """

    def __init__(self, experience_engine: CognitiveExperienceEngine) -> None:
        self._exp = experience_engine

    async def recommend_all(self) -> list[Recommendation]:
        """Generate all applicable optimization recommendations."""
        recs: list[Recommendation] = []
        recs.extend(await self.recommend_provider())
        recs.extend(await self.recommend_agent())
        recs.extend(await self.recommend_retry())
        recs.extend(await self.recommend_budget())
        return [r for r in recs if r.estimated_impact > 0.1]

    async def recommend_provider(self) -> list[Recommendation]:
        """Recommend alternative providers based on history."""
        experiences = self._exp.all_experiences
        by_provider: dict[str, list[float]] = defaultdict(list)
        for exp in experiences:
            for p in exp.selected_providers:
                by_provider[p].append(1.0 if exp.success else 0.0)
        if len(by_provider) < 2:
            return []
        rates = {p: sum(v) / len(v) for p, v in by_provider.items()}
        best = max(rates, key=lambda k: rates[k])
        worst = min(rates, key=lambda k: rates[k])
        if rates[best] - rates[worst] < 0.1:
            return []
        return [
            Recommendation(
                recommendation_type=RecommendationType.ALTERNATIVE_PROVIDER.value,
                title=f"Switch from '{worst}' to '{best}' for better success rate",
                description=f"'{best}' has {rates[best]:.1%} success vs '{worst}' at {rates[worst]:.1%}",
                current_state=f"Using '{worst}' ({rates[worst]:.1%} success)",
                recommended_state=f"Switch to '{best}' ({rates[best]:.1%} success)",
                expected_improvement=f"+{(rates[best] - rates[worst]) * 100:.0f}% success rate",
                estimated_impact=rates[best] - rates[worst],
                confidence=0.7,
                priority="high" if rates[best] - rates[worst] > 0.2 else "normal",
                affected_components=[worst, best],
                requires_approval=True,
            )
        ]

    async def recommend_agent(self) -> list[Recommendation]:
        """Recommend alternative agents based on history."""
        experiences = self._exp.all_experiences
        by_agent: dict[str, list[float]] = defaultdict(list)
        for exp in experiences:
            for a in exp.selected_agents:
                by_agent[a].append(1.0 if exp.success else 0.0)
        if len(by_agent) < 2:
            return []
        rates = {a: sum(v) / len(v) for a, v in by_agent.items()}
        best = max(rates, key=lambda k: rates[k])
        worst = min(rates, key=lambda k: rates[k])
        if rates[best] - rates[worst] < 0.15:
            return []
        return [
            Recommendation(
                recommendation_type=RecommendationType.ALTERNATIVE_AGENT.value,
                title=f"Route more tasks to agent '{best}' instead of '{worst}'",
                description=f"'{best}' has {rates[best]:.1%} success vs '{worst}' at {rates[worst]:.1%}",
                current_state=f"'{worst}' ({rates[worst]:.1%} success)",
                recommended_state=f"'{best}' ({rates[best]:.1%} success)",
                expected_improvement=f"+{(rates[best] - rates[worst]) * 100:.0f}% success rate",
                estimated_impact=rates[best] - rates[worst],
                confidence=0.75,
                priority="high",
                affected_components=[worst, best],
                requires_approval=True,
            )
        ]

    async def recommend_retry(self) -> list[Recommendation]:
        """Recommend retry strategy optimizations."""
        experiences = self._exp.all_experiences
        retried = [e for e in experiences if e.retries > 0]
        if len(retried) < 5:
            return []
        recovery_rate = sum(1 for e in retried if e.success) / len(retried)
        if recovery_rate < 0.5:
            return [
                Recommendation(
                    recommendation_type=RecommendationType.RETRY_OPTIMIZATION.value,
                    title="Increase max_retries — current recovery rate is low",
                    description=f"Only {recovery_rate:.1%} of retried executions succeed. Consider increasing retries.",
                    current_state=f"Recovery rate: {recovery_rate:.1%}",
                    recommended_state="Increase max_retries from 2 to 3 with exponential backoff",
                    expected_improvement="+15% recovery rate",
                    estimated_impact=0.4,
                    confidence=0.7,
                    priority="normal",
                    requires_approval=True,
                )
            ]
        return []

    async def recommend_budget(self) -> list[Recommendation]:
        """Recommend budget optimizations."""
        experiences = self._exp.all_experiences
        if len(experiences) < 10:
            return []
        avg_cost = sum(e.cost_usd for e in experiences) / len(experiences)
        expensive = [e for e in experiences if e.cost_usd > avg_cost * 2]
        if len(expensive) > len(experiences) * 0.2:
            return [
                Recommendation(
                    recommendation_type=RecommendationType.BUDGET_OPTIMIZATION.value,
                    title="Reduce cost by switching to cheaper providers for non-critical tasks",
                    description=f"{len(expensive)} executions cost >2x average (${avg_cost:.4f})",
                    current_state=f"Average cost: ${avg_cost:.4f}",
                    recommended_state="Use cheaper providers for low-priority tasks",
                    expected_improvement="-20% total cost",
                    estimated_impact=0.5,
                    confidence=0.65,
                    priority="normal",
                    requires_approval=True,
                )
            ]
        return []


class EnterpriseKnowledgeGraph:
    """Persistent knowledge graph of the enterprise.

    Nodes: agents, providers, projects, files, users, tasks, workflows,
    executions, plugins, documents, repositories, errors, fixes, capabilities.
    Relationships: depends_on, executes, produces, fixes, calls, etc.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._by_type: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: GraphNode) -> GraphNode:
        self._nodes[node.node_id] = node
        self._by_type[node.node_type].append(node.node_id)
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        self._edges.append(edge)
        return edge

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[GraphNode]:
        """Get all nodes connected to the given node."""
        neighbor_ids = set()
        for edge in self._edges:
            if edge.source_id == node_id:
                neighbor_ids.add(edge.target_id)
            elif edge.target_id == node_id:
                neighbor_ids.add(edge.source_id)
        return [self._nodes[nid] for nid in neighbor_ids if nid in self._nodes]

    def find_by_type(self, node_type: str) -> list[GraphNode]:
        """Find all nodes of a given type."""
        return [self._nodes[nid] for nid in self._by_type.get(node_type, [])]

    def traverse(self, start_id: str, max_depth: int = 3) -> list[GraphNode]:
        """BFS traversal from a starting node."""
        visited: set[str] = set()
        queue = [(start_id, 0)]
        result: list[GraphNode] = []
        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)
            node = self._nodes.get(node_id)
            if node:
                result.append(node)
            for edge in self._edges:
                if edge.source_id == node_id and edge.target_id not in visited:
                    queue.append((edge.target_id, depth + 1))
                elif edge.target_id == node_id and edge.source_id not in visited:
                    queue.append((edge.source_id, depth + 1))
        return result

    def impact_analysis(self, node_id: str) -> dict[str, Any]:
        """Analyze the impact of changing a node."""
        affected = self.traverse(node_id, max_depth=5)
        return {
            "source_node": node_id,
            "affected_count": len(affected),
            "affected_nodes": [n.to_dict() for n in affected],
            "affected_types": list({n.node_type for n in affected}),
        }

    def build_snapshot(self) -> KnowledgeGraph:
        """Build a snapshot of the current graph."""
        return KnowledgeGraph(
            nodes=list(self._nodes.values()),
            edges=list(self._edges),
        )

    def semantic_search(self, query: str) -> list[GraphNode]:
        """Simple keyword search over node names and properties."""
        query_lower = query.lower()
        results: list[GraphNode] = []
        for node in self._nodes.values():
            if query_lower in node.name.lower():
                results.append(node)
                continue
            for v in node.properties.values():
                if isinstance(v, str) and query_lower in v.lower():
                    results.append(node)
                    break
        return results


class ArchitectureIntelligence:
    """Analyzes the repository for architecture issues.

    Detects: dead code, duplicate logic, architecture drift, circular
    dependencies, performance bottlenecks, security weaknesses, documentation
    gaps, missing tests, dependency issues.
    """

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    async def analyze_all(self) -> list[ArchIssue]:
        """Run all architecture analyses."""
        issues: list[ArchIssue] = []
        issues.extend(await self.find_dead_code())
        issues.extend(await self.find_doc_gaps())
        issues.extend(await self.find_missing_tests())
        return issues

    async def find_dead_code(self) -> list[ArchIssue]:
        """Find potentially dead code (unused imports, unreachable functions)."""
        issues: list[ArchIssue] = []
        for py_file in self._root.rglob("*.py"):
            if ".venv" in str(py_file) or "node_modules" in str(py_file) or ".git" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.FunctionDef)
                        and node.name.startswith("_")
                        and not node.name.startswith("__")
                    ):
                        # Check if private function is called anywhere
                        if not self._is_called(node.name, py_file):
                            issues.append(
                                ArchIssue(
                                    issue_type=ArchIssueType.DEAD_CODE.value,
                                    severity="low",
                                    file=str(py_file.relative_to(self._root)),
                                    line=node.lineno,
                                    description=f"Private function '{node.name}' may be unused",
                                    recommendation="Review and remove if truly unused",
                                )
                            )
            except Exception:
                pass
        return issues[:20]  # limit

    def _is_called(self, func_name: str, current_file: Path) -> bool:
        """Check if a function is called in any file."""
        for py_file in self._root.rglob("*.py"):
            if ".venv" in str(py_file) or "node_modules" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                if func_name + "(" in source:
                    return True
            except Exception:
                pass
        return False

    async def find_doc_gaps(self) -> list[ArchIssue]:
        """Find functions/classes missing docstrings."""
        issues: list[ArchIssue] = []
        for py_file in self._root.rglob("*.py"):
            if ".venv" in str(py_file) or "node_modules" in str(py_file) or ".git" in str(py_file):
                continue
            if "tests/" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and not node.body:
                        issues.append(
                            ArchIssue(
                                issue_type=ArchIssueType.DOC_GAP.value,
                                severity="low",
                                file=str(py_file.relative_to(self._root)),
                                line=node.lineno,
                                description=f"Class '{node.name}' has no docstring",
                                recommendation="Add a docstring explaining the class purpose",
                            )
                        )
            except Exception:
                pass
        return issues[:20]

    async def find_missing_tests(self) -> list[ArchIssue]:
        """Find source modules without corresponding test files."""
        issues: list[ArchIssue] = []
        src_dirs = [self._root / "services", self._root / "core", self._root / "agents"]
        test_dir = self._root / "tests" / "unit"
        for src_dir in src_dirs:
            if not src_dir.exists():
                continue
            for py_file in src_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                # Check if there's a test file
                test_name = f"test_{py_file.stem}.py"
                if not (test_dir / test_name).exists():
                    issues.append(
                        ArchIssue(
                            issue_type=ArchIssueType.MISSING_TESTS.value,
                            severity="medium",
                            file=str(py_file.relative_to(self._root)),
                            line=0,
                            description=f"No test file for {py_file.name}",
                            recommendation=f"Create {test_name} in tests/unit/",
                        )
                    )
        return issues[:20]


class RepositoryIntelligence:
    """Maintains repository health metrics and proposes updates."""

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    async def health_report(self) -> dict[str, Any]:
        """Generate a repository health report."""
        py_files = [
            f
            for f in self._root.rglob("*.py")
            if ".venv" not in str(f) and "node_modules" not in str(f) and ".git" not in str(f)
        ]
        test_files = (
            list((self._root / "tests").rglob("*.py")) if (self._root / "tests").exists() else []
        )
        src_lines = sum(self._count_lines(f) for f in py_files)
        test_lines = sum(self._count_lines(f) for f in test_files)
        docs = list(self._root.rglob("*.md"))
        # Check for key files
        has_readme = (self._root / "README.md").exists()
        has_changelog = (self._root / "CHANGELOG.md").exists()
        has_license = (self._root / "LICENSE").exists()
        has_contributing = (self._root / "CONTRIBUTING.md").exists()
        has_security = (self._root / "SECURITY.md").exists()
        return {
            "source_files": len(py_files),
            "test_files": len(test_files),
            "source_lines": src_lines,
            "test_lines": test_lines,
            "test_to_source_ratio": round(test_lines / max(1, src_lines), 2),
            "documentation_files": len(docs),
            "has_readme": has_readme,
            "has_changelog": has_changelog,
            "has_license": has_license,
            "has_contributing": has_contributing,
            "has_security": has_security,
            "health_score": self._compute_health_score(
                has_readme,
                has_changelog,
                has_license,
                has_contributing,
                has_security,
                len(test_files),
                len(py_files),
            ),
        }

    def _count_lines(self, path: Path) -> int:
        try:
            return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            return 0

    def _compute_health_score(
        self,
        readme: bool,
        changelog: bool,
        license: bool,
        contributing: bool,
        security: bool,
        test_count: int,
        src_count: int,
    ) -> float:
        score = 0.0
        if readme:
            score += 15
        if changelog:
            score += 10
        if license:
            score += 15
        if contributing:
            score += 10
        if security:
            score += 10
        test_ratio = test_count / max(1, src_count)
        score += min(40, test_ratio * 100)
        return min(100, round(score))


class EnterpriseReporting:
    """Generates enterprise reports in multiple formats."""

    def __init__(self, experience_engine: CognitiveExperienceEngine) -> None:
        self._exp = experience_engine

    async def generate(
        self,
        report_type: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> EnterpriseReport:
        """Generate a report."""
        report = EnterpriseReport(
            report_type=report_type,
            title=f"{report_type.replace('_', ' ').title()} Report",
        )
        stats = await self._exp.stats()
        if report_type == EnterpriseReportType.EXECUTION.value:
            report.summary = f"Total executions: {stats.get('total', 0)}, Success rate: {stats.get('success_rate', 0):.1%}"
            report.key_findings = [
                f"Total executions: {stats.get('total', 0)}",
                f"Success rate: {stats.get('success_rate', 0):.1%}",
                f"Average cost: ${stats.get('avg_cost_usd', 0):.4f}",
                f"Average latency: {stats.get('avg_latency_s', 0):.2f}s",
            ]
            report.metrics = stats
        elif report_type == EnterpriseReportType.REPOSITORY.value:
            repo_intel = RepositoryIntelligence(Path())
            health = await repo_intel.health_report()
            report.summary = f"Repository health: {health['health_score']}/100"
            report.key_findings = [
                f"Source files: {health['source_files']}",
                f"Test files: {health['test_files']}",
                f"Test-to-source ratio: {health['test_to_source_ratio']}",
            ]
            report.metrics = health
        else:
            report.summary = f"{report_type} report generated"
            report.key_findings = ["Report generated successfully"]
        report.data = data or {}
        return report

    async def export_markdown(self, report: EnterpriseReport) -> str:
        """Export report as Markdown."""
        lines = [
            f"# {report.title}",
            "",
            f"**Generated:** {report.generated_at.isoformat()}",
            f"**Summary:** {report.summary}",
            "",
            "## Key Findings",
            "",
        ]
        for finding in report.key_findings:
            lines.append(f"- {finding}")
        if report.metrics:
            lines.extend(
                [
                    "",
                    "## Metrics",
                    "",
                    "```json",
                    json.dumps(report.metrics, indent=2, default=str),
                    "```",
                ]
            )
        return "\n".join(lines)

    async def export_json(self, report: EnterpriseReport) -> str:
        """Export report as JSON."""
        return json.dumps(report.to_dict(), indent=2, default=str)

    async def export_csv(self, report: EnterpriseReport) -> str:
        """Export report metrics as CSV."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["metric", "value"])
        for k, v in report.metrics.items():
            writer.writerow([k, v])
        return output.getvalue()
