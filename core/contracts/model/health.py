"""Provider health contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.timestamp import utc_now

__all__ = ["ProviderHealth", "ProviderStatus"]


class ProviderStatus(StrEnum):
    """Provider health states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # some requests failing, but still usable
    UNHEALTHY = "unhealthy"  # all requests failing; failover to next provider
    DISABLED = "disabled"  # manually disabled by the operator


class ProviderHealth(BaseModel):
    """Per-provider health report."""

    model_config = ConfigDict(frozen=True)

    provider: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    # Rolling window stats
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    avg_latency_s: float = Field(default=0.0, ge=0.0)
    p95_latency_s: float = Field(default=0.0, ge=0.0)
    # Consecutive failure count (for auto-disable)
    consecutive_failures: int = Field(default=0, ge=0)
    # Last error
    last_error: str | None = None
    last_error_at: datetime | None = None
    # When the provider was last healthy
    last_healthy_at: datetime | None = None
    checked_at: datetime = Field(default_factory=utc_now)
