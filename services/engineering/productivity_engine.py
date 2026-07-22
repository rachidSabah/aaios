"""Phase 22 — Developer Productivity Engine.

Measures engineering productivity using DORA metrics (deployment frequency,
lead time, change failure rate, recovery time) plus cycle time, review time,
planning accuracy, testing efficiency, and documentation completion.
Generates dashboards, trends, and optimization recommendations.

READ-ONLY — never modifies any system. Recommendations require human approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "DORAMetrics",
    "ProductivityDashboard",
    "ProductivityMetrics",
    "ProductivityReport",
    "ProductivityTrend",
    "DeveloperProductivityEngine",
]


@dataclass
class DORAMetrics:
    """The four DORA metrics for a period."""

    deployment_frequency: float = 0.0  # deploys per day
    lead_time_hours: float = 0.0  # avg lead time (commit → deploy)
    change_failure_rate: float = 0.0  # 0..1
    recovery_time_hours: float = 0.0  # avg MTTR
    elite: bool = False
    level: str = "low"  # low | medium | high | elite

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_frequency": round(self.deployment_frequency, 4),
            "lead_time_hours": round(self.lead_time_hours, 2),
            "change_failure_rate": round(self.change_failure_rate, 4),
            "recovery_time_hours": round(self.recovery_time_hours, 2),
            "elite": self.elite,
            "level": self.level,
        }


@dataclass
class ProductivityMetrics:
    """Engineering productivity metrics for a period."""

    cycle_time_hours: float = 0.0  # issue start → merge
    lead_time_hours: float = 0.0  # first commit → deploy
    review_time_hours: float = 0.0  # PR open → merge
    deployment_frequency: float = 0.0  # per day
    change_failure_rate: float = 0.0  # 0..1
    recovery_time_hours: float = 0.0  # MTTR
    planning_accuracy: float = 0.0  # 0..1, planned vs actual
    testing_efficiency: float = 0.0  # 0..1, test pass rate / flake rate
    documentation_completion: float = 0.0  # 0..1

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_time_hours": round(self.cycle_time_hours, 2),
            "lead_time_hours": round(self.lead_time_hours, 2),
            "review_time_hours": round(self.review_time_hours, 2),
            "deployment_frequency": round(self.deployment_frequency, 4),
            "change_failure_rate": round(self.change_failure_rate, 4),
            "recovery_time_hours": round(self.recovery_time_hours, 2),
            "planning_accuracy": round(self.planning_accuracy, 4),
            "testing_efficiency": round(self.testing_efficiency, 4),
            "documentation_completion": round(self.documentation_completion, 4),
        }


@dataclass
class ProductivityTrend:
    """A single point in a productivity trend."""

    period: str = ""  # e.g. "2025-W03" or "2025-01"
    metrics: ProductivityMetrics = field(default_factory=ProductivityMetrics)
    dora: DORAMetrics = field(default_factory=DORAMetrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "metrics": self.metrics.to_dict(),
            "dora": self.dora.to_dict(),
        }


@dataclass
class ProductivityDashboard:
    """Dashboard view of developer productivity."""

    dashboard_id: str = field(default_factory=lambda: uuid4().hex[:12])
    current: ProductivityMetrics = field(default_factory=ProductivityMetrics)
    dora: DORAMetrics = field(default_factory=DORAMetrics)
    trends: list[ProductivityTrend] = field(default_factory=list)
    optimization_opportunities: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dashboard_id": self.dashboard_id,
            "current": self.current.to_dict(),
            "dora": self.dora.to_dict(),
            "trends": [t.to_dict() for t in self.trends],
            "optimization_opportunities": list(self.optimization_opportunities),
            "recommendations": list(self.recommendations),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ProductivityReport:
    """A complete productivity report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    period_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = field(default_factory=lambda: datetime.now(UTC))
    metrics: ProductivityMetrics = field(default_factory=ProductivityMetrics)
    dora: DORAMetrics = field(default_factory=DORAMetrics)
    trends: list[ProductivityTrend] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    requires_approval: bool = True
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metrics": self.metrics.to_dict(),
            "dora": self.dora.to_dict(),
            "trends": [t.to_dict() for t in self.trends],
            "recommendations": list(self.recommendations),
            "confidence": round(self.confidence, 4),
            "requires_approval": self.requires_approval,
            "generated_at": self.generated_at.isoformat(),
        }


class DeveloperProductivityEngine:
    """Phase 22 — Developer Productivity Engine.

    Accepts events as input (commits, deploys, PR merges, incidents, planning
    completions, test runs). Never accesses production systems directly.
    """

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    # --- public API -----------------------------------------------------

    def record_event(self, event: dict[str, Any]) -> None:
        """Record a productivity event.

        Event types: commit, pr_opened, pr_merged, deploy, incident,
        incident_resolved, plan_completed, test_run, doc_updated.
        """
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(UTC).isoformat()
        if "type" not in event:
            event["type"] = "unknown"
        self._events.append(event)

    def record_events(self, events: list[dict[str, Any]]) -> None:
        """Record multiple events."""
        for e in events:
            self.record_event(e)

    async def metrics(
        self,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> ProductivityMetrics:
        """Compute productivity metrics for a period."""
        end = period_end or datetime.now(UTC)
        start = period_start or (end - timedelta(days=30))
        events = [e for e in self._events if start <= self._parse_ts(e["timestamp"]) <= end]
        m = ProductivityMetrics()
        # Cycle time: avg (issue_start → pr_merged) if both recorded
        cycle_times: list[float] = []
        pr_opens = {e["pr_id"]: e for e in events if e["type"] == "pr_opened" and "pr_id" in e}
        for e in events:
            if e["type"] == "pr_merged" and "pr_id" in e:
                open_ev = pr_opens.get(e["pr_id"])
                if open_ev:
                    delta = self._parse_ts(e["timestamp"]) - self._parse_ts(open_ev["timestamp"])
                    cycle_times.append(delta.total_seconds() / 3600.0)
        if cycle_times:
            m.cycle_time_hours = sum(cycle_times) / len(cycle_times)
        # Review time: avg (pr_opened → pr_merged)
        review_times: list[float] = []
        for e in events:
            if e["type"] == "pr_merged" and "pr_id" in e:
                open_ev = pr_opens.get(e["pr_id"])
                if open_ev:
                    delta = self._parse_ts(e["timestamp"]) - self._parse_ts(open_ev["timestamp"])
                    review_times.append(delta.total_seconds() / 3600.0)
        if review_times:
            m.review_time_hours = sum(review_times) / len(review_times)
        # Lead time: avg (commit → deploy)
        lead_times: list[float] = []
        commits = [e for e in events if e["type"] == "commit"]
        deploys = [e for e in events if e["type"] == "deploy"]
        for d in deploys:
            d_ts = self._parse_ts(d["timestamp"])
            prior_commits = [c for c in commits if self._parse_ts(c["timestamp"]) <= d_ts]
            if prior_commits:
                earliest = min(self._parse_ts(c["timestamp"]) for c in prior_commits)
                lead_times.append((d_ts - earliest).total_seconds() / 3600.0)
        if lead_times:
            m.lead_time_hours = sum(lead_times) / len(lead_times)
        # Deployment frequency
        days = max(1, (end - start).days)
        m.deployment_frequency = len(deploys) / days
        # Change failure rate: incidents / deploys
        incidents = [e for e in events if e["type"] == "incident"]
        if deploys:
            m.change_failure_rate = len(incidents) / len(deploys)
        # Recovery time: avg (incident → incident_resolved)
        recovery_times: list[float] = []
        incident_opens = {e["incident_id"]: e for e in incidents if "incident_id" in e}
        for e in events:
            if e["type"] == "incident_resolved" and "incident_id" in e:
                open_ev = incident_opens.get(e["incident_id"])
                if open_ev:
                    delta = self._parse_ts(e["timestamp"]) - self._parse_ts(open_ev["timestamp"])
                    recovery_times.append(delta.total_seconds() / 3600.0)
        if recovery_times:
            m.recovery_time_hours = sum(recovery_times) / len(recovery_times)
        # Planning accuracy
        plan_completed = [e for e in events if e["type"] == "plan_completed"]
        if plan_completed:
            accs = [e.get("accuracy", 0.0) for e in plan_completed]
            m.planning_accuracy = sum(accs) / len(accs)
        # Testing efficiency
        test_runs = [e for e in events if e["type"] == "test_run"]
        if test_runs:
            passed = sum(1 for e in test_runs if e.get("passed", False))
            m.testing_efficiency = passed / len(test_runs)
        # Documentation completion
        doc_events = [e for e in events if e["type"] == "doc_updated"]
        if doc_events:
            completions = [e.get("completion", 0.0) for e in doc_events]
            m.documentation_completion = sum(completions) / len(completions)
        return m

    async def dora(
        self,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> DORAMetrics:
        """Compute DORA metrics and classify the team."""
        m = await self.metrics(period_start, period_end)
        d = DORAMetrics(
            deployment_frequency=m.deployment_frequency,
            lead_time_hours=m.lead_time_hours,
            change_failure_rate=m.change_failure_rate,
            recovery_time_hours=m.recovery_time_hours,
        )
        # DORA level classification
        if (
            d.deployment_frequency >= 1.0  # multiple deploys per day
            and d.lead_time_hours <= 24
            and d.change_failure_rate <= 0.15
            and d.recovery_time_hours <= 1
        ):
            d.level = "elite"
            d.elite = True
        elif (
            d.deployment_frequency >= 1 / 7  # weekly
            and d.lead_time_hours <= 24 * 7
            and d.change_failure_rate <= 0.3
            and d.recovery_time_hours <= 24
        ):
            d.level = "high"
        elif (
            d.deployment_frequency >= 1 / 30  # monthly
            and d.lead_time_hours <= 24 * 30
            and d.change_failure_rate <= 0.5
            and d.recovery_time_hours <= 24 * 7
        ):
            d.level = "medium"
        else:
            d.level = "low"
        return d

    async def trends(self, periods: int = 8) -> list[ProductivityTrend]:
        """Build a trend over the last ``periods`` weeks."""
        out: list[ProductivityTrend] = []
        now = datetime.now(UTC)
        for i in range(periods, 0, -1):
            end = now - timedelta(weeks=i - 1)
            start = end - timedelta(weeks=1)
            m = await self.metrics(start, end)
            d = await self.dora(start, end)
            out.append(
                ProductivityTrend(
                    period=start.strftime("%Y-W%U"),
                    metrics=m,
                    dora=d,
                )
            )
        return out

    async def dashboard(self) -> ProductivityDashboard:
        """Build a productivity dashboard."""
        dash = ProductivityDashboard()
        dash.current = await self.metrics()
        dash.dora = await self.dora()
        dash.trends = await self.trends()
        dash.optimization_opportunities = self._opportunities(dash.current, dash.dora)
        dash.recommendations = self._recommendations(dash.current, dash.dora)
        return dash

    async def report(self) -> ProductivityReport:
        """Generate a full productivity report."""
        now = datetime.now(UTC)
        start = now - timedelta(days=30)
        return ProductivityReport(
            period_start=start,
            period_end=now,
            metrics=await self.metrics(start, now),
            dora=await self.dora(start, now),
            trends=await self.trends(),
            recommendations=[
                {"text": r, "confidence": 0.7, "requires_approval": True}
                for r in self._recommendations(
                    await self.metrics(start, now), await self.dora(start, now)
                )
            ],
            confidence=0.7,
        )

    # --- helpers --------------------------------------------------------

    def _parse_ts(self, ts: str | datetime) -> datetime:
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return datetime.now(UTC)

    def _opportunities(self, m: ProductivityMetrics, d: DORAMetrics) -> list[dict[str, Any]]:
        opps: list[dict[str, Any]] = []
        if d.deployment_frequency < 1 / 7:
            opps.append(
                {
                    "metric": "deployment_frequency",
                    "current": d.deployment_frequency,
                    "target": 1.0,
                    "impact": "high",
                    "effort": "medium",
                    "description": "Move from weekly to daily deploys via CI/CD automation.",
                }
            )
        if d.lead_time_hours > 168:
            opps.append(
                {
                    "metric": "lead_time",
                    "current": d.lead_time_hours,
                    "target": 24.0,
                    "impact": "high",
                    "effort": "medium",
                    "description": "Reduce lead time by batching smaller PRs and automating tests.",
                }
            )
        if d.change_failure_rate > 0.2:
            opps.append(
                {
                    "metric": "change_failure_rate",
                    "current": d.change_failure_rate,
                    "target": 0.1,
                    "impact": "high",
                    "effort": "high",
                    "description": "Reduce failures via stronger pre-prod testing and canary deploys.",
                }
            )
        if d.recovery_time_hours > 24:
            opps.append(
                {
                    "metric": "recovery_time",
                    "current": d.recovery_time_hours,
                    "target": 1.0,
                    "impact": "medium",
                    "effort": "medium",
                    "description": "Improve MTTR via better observability and runbooks.",
                }
            )
        if m.review_time_hours > 48:
            opps.append(
                {
                    "metric": "review_time",
                    "current": m.review_time_hours,
                    "target": 8.0,
                    "impact": "medium",
                    "effort": "low",
                    "description": "Set review SLAs and rotate reviewers.",
                }
            )
        if m.planning_accuracy < 0.7:
            opps.append(
                {
                    "metric": "planning_accuracy",
                    "current": m.planning_accuracy,
                    "target": 0.85,
                    "impact": "medium",
                    "effort": "low",
                    "description": "Improve estimation by decomposing stories and tracking velocity.",
                }
            )
        return opps

    def _recommendations(self, m: ProductivityMetrics, d: DORAMetrics) -> list[str]:
        recs: list[str] = []
        if d.level == "elite":
            recs.append("Sustain elite DORA performance — share practices with other teams.")
        else:
            recs.append(f"Current DORA level: {d.level}. Target the next level.")
        if d.deployment_frequency < 1 / 7:
            recs.append("Adopt continuous deployment for low-risk changes.")
        if m.review_time_hours > 24:
            recs.append("Reduce PR review time by setting a 24h SLA.")
        if m.testing_efficiency < 0.9:
            recs.append("Stabilize the test suite — current pass rate is below 90%.")
        if m.documentation_completion < 0.7:
            recs.append("Increase documentation completion — currently below 70%.")
        if m.planning_accuracy < 0.7:
            recs.append("Calibrate planning estimates against actuals each sprint.")
        if not recs:
            recs.append("Productivity posture is healthy — continue regular reviews.")
        return recs
