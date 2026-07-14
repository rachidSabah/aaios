"""Metrics report — returned by ``GenericAgent.report_metrics()``.

Used by the Telemetry service and the dashboard's per-agent analytics.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.timestamp import utc_now


class MetricsReport(BaseModel):
    """Operational metrics for an agent."""

    model_config = ConfigDict(frozen=True)

    agent_id: str
    reported_at: datetime = Field(default_factory=utc_now)
    tasks_completed: int = Field(default=0, ge=0)
    tasks_failed: int = Field(default=0, ge=0)
    tasks_cancelled: int = Field(default=0, ge=0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    p99_latency_ms: float = Field(default=0.0, ge=0.0)
    tokens_consumed: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    custom_metrics: dict[str, float | int | str] = Field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Return the success rate (0.0 - 1.0). Returns 1.0 if no tasks."""
        total = self.tasks_completed + self.tasks_failed + self.tasks_cancelled
        if total == 0:
            return 1.0
        return self.tasks_completed / total
