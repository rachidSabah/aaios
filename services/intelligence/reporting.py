"""Reporting Engine — generates daily/weekly/monthly/reliability/optimization/risk/mission reports.

Reports are comprehensive intelligence documents combining health scores,
forecasts, recommendations, risks, capacity, and cost analysis into a
single narrative with key findings and action items.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.logging import get_logger
from services.intelligence.models import (
    CapacityForecast,
    CostBreakdown,
    EnterpriseHealthScore,
    ForecastResult,
    IntelligenceReport,
    IntelligenceReportType,
    OperationalMetrics,
    OptimizationRecommendation,
    RiskAssessment,
)

_log = get_logger(__name__)

__all__ = ["ReportingEngine"]


class ReportingEngine:
    """Generates intelligence reports.

    Each report type has a different time horizon and focus:
      - daily_executive: 24h, high-level health + action items
      - weekly_operations: 7d, operational metrics + trends
      - monthly_performance: 30d, performance + cost analysis
      - reliability: reliability scores + failure analysis
      - optimization: all pending recommendations
      - risk: all detected risks + heat map
      - mission: per-mission analytics
    """

    def generate(
        self,
        report_type: str,
        *,
        health: EnterpriseHealthScore,
        metrics: OperationalMetrics,
        forecasts: list[ForecastResult] | None = None,
        recommendations: list[OptimizationRecommendation] | None = None,
        risks: list[RiskAssessment] | None = None,
        capacity: list[CapacityForecast] | None = None,
        cost: CostBreakdown | None = None,
    ) -> IntelligenceReport:
        """Generate an intelligence report."""
        now = datetime.now(UTC)
        if report_type == IntelligenceReportType.DAILY_EXECUTIVE.value:
            period_start = now - timedelta(days=1)
        elif report_type == IntelligenceReportType.WEEKLY_OPERATIONS.value:
            period_start = now - timedelta(days=7)
        elif report_type == IntelligenceReportType.MONTHLY_PERFORMANCE.value:
            period_start = now - timedelta(days=30)
        else:
            period_start = now - timedelta(days=1)

        report = IntelligenceReport(
            report_type=report_type,
            generated_at=now,
            period_start=period_start,
            period_end=now,
            health_score=health,
            operational_metrics=metrics,
            forecasts=forecasts or [],
            recommendations=recommendations or [],
            risks=risks or [],
            capacity=capacity or [],
            cost=cost or CostBreakdown(),
        )

        # Generate summary + key findings + action items
        report.summary = self._generate_summary(report)
        report.key_findings = self._generate_key_findings(report)
        report.action_items = self._generate_action_items(report)

        _log.info(
            "Generated %s report: health=%.2f (%s), %d findings, %d actions",
            report_type, health.overall_score, health.grade,
            len(report.key_findings), len(report.action_items),
        )
        return report

    def _generate_summary(self, report: IntelligenceReport) -> str:
        """Generate a narrative summary."""
        h = report.health_score
        m = report.operational_metrics
        summary = (
            f"Enterprise health is {h.status} (score: {h.overall_score:.2f}, grade: {h.grade}). "
            f"Currently tracking {m.total_missions} missions ({m.active_missions} active) "
            f"with {m.total_agents} agents ({m.active_agents} active). "
            f"Budget utilization: {m.total_spent_usd / max(1, m.total_budget_usd) * 100:.0f}%. "
        )
        if report.forecasts:
            high_risk = [f for f in report.forecasts if f.probability > 0.5]
            if high_risk:
                summary += f"{len(high_risk)} high-probability forecasts detected. "
        if report.risks:
            critical = [r for r in report.risks if r.level == "critical"]
            if critical:
                summary += f"{len(critical)} critical risks require attention. "
        if report.recommendations:
            summary += f"{len(report.recommendations)} optimization recommendations available. "
        return summary.strip()

    def _generate_key_findings(self, report: IntelligenceReport) -> list[str]:
        """Generate key findings from the report data."""
        findings: list[str] = []
        h = report.health_score
        m = report.operational_metrics

        # Health findings
        if h.overall_score < 0.7:
            findings.append(f"Overall health is {h.status} ({h.overall_score:.2f}) — below target of 0.80")
        if h.operational < 0.7:
            findings.append(f"Operational health is degraded ({h.operational:.2f})")
        if h.cost_efficiency < 0.3:
            findings.append(f"Cost efficiency is low ({h.cost_efficiency:.2f}) — budget utilization high")

        # Mission findings
        if m.active_missions > 0 and m.avg_mission_completion_pct < 50:
            findings.append(f"Active missions averaging only {m.avg_mission_completion_pct:.0f}% completion")

        # Forecast findings
        for f in report.forecasts:
            if f.probability > 0.5:
                findings.append(f"High-probability forecast: {f.prediction}")

        # Risk findings
        critical_risks = [r for r in report.risks if r.level == "critical"]
        if critical_risks:
            findings.append(f"{len(critical_risks)} critical risks detected")

        # Cost findings
        if report.cost.budget_utilization_pct > 80:
            findings.append(f"Budget utilization at {report.cost.budget_utilization_pct:.0f}% — approaching limit")

        if not findings:
            findings.append("System is operating within normal parameters — no issues detected")
        return findings

    def _generate_action_items(self, report: IntelligenceReport) -> list[str]:
        """Generate action items from recommendations + risks."""
        actions: list[str] = []

        # From critical risks
        for risk in report.risks:
            if risk.level == "critical" and risk.mitigation:
                actions.append(f"[CRITICAL] {risk.description} — Mitigation: {risk.mitigation}")

        # From high-priority recommendations
        for rec in report.recommendations:
            if rec.priority in ("critical", "high"):
                actions.append(f"[{rec.priority.upper()}] {rec.title} — {rec.expected_improvement}")

        # From high-probability forecasts
        for f in report.forecasts:
            if f.probability > 0.6 and f.recommended_actions:
                actions.append(f"[FORECAST] {f.prediction} — {f.recommended_actions[0]}")

        if not actions:
            actions.append("No immediate action required — continue monitoring")
        return actions
