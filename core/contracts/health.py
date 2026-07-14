"""Health contracts — used by every component that exposes a health check."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from core.contracts.timestamp import utc_now


class HealthState(StrEnum):
    """Three-tier health state."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthReport(BaseModel):
    """The result of a component health check."""

    state: HealthState
    reason: str = Field(default="", description="Human-readable explanation.")
    failing_subsystems: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=utc_now)
    latency_ms: float = Field(default=0.0, description="Time the check took, in ms.")

    @classmethod
    def healthy(cls, latency_ms: float = 0.0) -> HealthReport:
        """Return a healthy report."""
        return cls(state=HealthState.HEALTHY, latency_ms=latency_ms)

    @classmethod
    def degraded(cls, reason: str, failing: list[str] | None = None) -> HealthReport:
        """Return a degraded report."""
        return cls(
            state=HealthState.DEGRADED,
            reason=reason,
            failing_subsystems=failing or [],
        )

    @classmethod
    def unhealthy(cls, reason: str, failing: list[str] | None = None) -> HealthReport:
        """Return an unhealthy report."""
        return cls(
            state=HealthState.UNHEALTHY,
            reason=reason,
            failing_subsystems=failing or [],
        )
