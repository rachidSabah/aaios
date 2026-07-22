"""Cognitive Intelligence Manager — top-level facade for v5.0.

Wires together all cognitive modules:
  - CognitiveExperienceEngine (Module 1)
  - CognitiveLearningEngine (Module 2)
  - CognitivePredictionEngine (Module 3)
  - CognitiveOptimizationEngine (Module 4)
  - EnterpriseKnowledgeGraph (Module 5)
  - ArchitectureIntelligence (Module 7)
  - RepositoryIntelligence (Module 8)
  - EnterpriseReporting (Module 10)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.logging import get_logger
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
from services.cognitive.models import (
    EnterpriseReportType,
)

_log = get_logger(__name__)

__all__ = ["CognitiveManager"]


class CognitiveManager:
    """Top-level facade for the Enterprise Cognitive Intelligence Platform.

    Usage:
        mgr = CognitiveManager()
        await mgr.record_experience(exp)
        insights = await mgr.learn()
        predictions = await mgr.predict(context)
        recs = await mgr.optimize()
        report = await mgr.generate_report("execution")
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self.experience = CognitiveExperienceEngine()
        self.learning = CognitiveLearningEngine(self.experience)
        self.prediction = CognitivePredictionEngine(self.experience)
        self.optimization = CognitiveOptimizationEngine(self.experience)
        self.knowledge_graph = EnterpriseKnowledgeGraph()
        self.architecture = ArchitectureIntelligence(repo_root or Path())
        self.repository = RepositoryIntelligence(repo_root or Path())
        self.reporting = EnterpriseReporting(self.experience)

    # Module 1: Experience
    async def record_experience(self, exp: CognitiveExperience) -> CognitiveExperience:
        return await self.experience.record(exp)

    async def search_experiences(self, **kwargs: Any) -> list[dict[str, Any]]:
        exps = await self.experience.search(**kwargs)
        return [e.to_dict() for e in exps]

    async def experience_timeline(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self.experience.timeline(limit=limit)

    async def experience_stats(self) -> dict[str, Any]:
        return await self.experience.stats()

    async def experience_export(self, format: str = "json") -> str:
        if format == "csv":
            return await self.experience.export_csv()
        return await self.experience.export_json()

    async def experience_replay(self, experience_id: str) -> dict[str, Any]:
        return await self.experience.replay(experience_id)

    # Module 2: Learning
    async def learn(self) -> list[dict[str, Any]]:
        insights = await self.learning.learn_all()
        return [i.to_dict() for i in insights]

    async def learning_metrics(self) -> list[dict[str, Any]]:
        metrics = await self.learning.metrics()
        return [m.to_dict() for m in metrics]

    # Module 3: Prediction
    async def predict(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        predictions = await self.prediction.predict_all(context)
        return [p.to_dict() for p in predictions]

    # Module 4: Optimization
    async def optimize(self) -> list[dict[str, Any]]:
        recs = await self.optimization.recommend_all()
        return [r.to_dict() for r in recs]

    # Module 5: Knowledge Graph
    def add_graph_node(self, node: Any) -> dict[str, Any]:
        from services.cognitive.models import GraphNode

        if isinstance(node, dict):
            graph_node = GraphNode(**node)
        else:
            graph_node = node
        self.knowledge_graph.add_node(graph_node)
        return graph_node.to_dict()

    def graph_snapshot(self) -> dict[str, Any]:
        return self.knowledge_graph.build_snapshot().to_dict()

    def graph_impact_analysis(self, node_id: str) -> dict[str, Any]:
        return self.knowledge_graph.impact_analysis(node_id)

    def graph_search(self, query: str) -> list[dict[str, Any]]:
        results = self.knowledge_graph.semantic_search(query)
        return [n.to_dict() for n in results]

    # Module 7: Architecture Intelligence
    async def arch_analyze(self) -> list[dict[str, Any]]:
        issues = await self.architecture.analyze_all()
        return [i.to_dict() for i in issues]

    # Module 8: Repository Intelligence
    async def repo_health(self) -> dict[str, Any]:
        return await self.repository.health_report()

    # Module 10: Reporting
    async def generate_report(
        self,
        report_type: str = EnterpriseReportType.EXECUTION.value,
    ) -> dict[str, Any]:
        report = await self.reporting.generate(report_type)
        return report.to_dict()

    async def export_report(
        self,
        report_type: str = EnterpriseReportType.EXECUTION.value,
        format: str = "json",
    ) -> str:
        report = await self.reporting.generate(report_type)
        if format == "markdown":
            return await self.reporting.export_markdown(report)
        if format == "csv":
            return await self.reporting.export_csv(report)
        return await self.reporting.export_json(report)

    async def get_all(self) -> dict[str, Any]:
        """Get all cognitive data in one response."""
        return {
            "experience_stats": await self.experience_stats(),
            "learning_insights": await self.learn(),
            "learning_metrics": await self.learning_metrics(),
            "predictions": await self.predict({}),
            "recommendations": await self.optimize(),
            "knowledge_graph": self.graph_snapshot(),
            "architecture_issues": await self.arch_analyze(),
            "repository_health": await self.repo_health(),
        }
