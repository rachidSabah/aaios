"""Monitoring models — Pydantic definitions for continuous health monitoring and alerting."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AlertSeverity(StrEnum):
    """Health monitor alert severity levels."""

    WARNING = "warning"
    CRITICAL = "critical"
    FAILURE = "failure"
    RECOVERY = "recovery"
    DEGRADATION = "degradation"


class AlertChannel(StrEnum):
    """Supported alerting dispatch channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    DESKTOP = "desktop"
    CLI = "cli"


class SystemMetrics(BaseModel):
    """Observed system metrics snapshot."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    gpu_load_percent: float | None = None
    network_latency_ms: float = 0.0


class ComponentStatus(BaseModel):
    """Detailed health status of a single runtime component."""

    name: str
    status: str  # healthy, warning, critical, offline
    latency_ms: float = 0.0
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthAlert(BaseModel):
    """An alert notification dispatched on threshold breach or system recovery."""

    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    component: str
    severity: AlertSeverity
    message: str
    evidence: str
    dispatched_channels: list[AlertChannel] = Field(default_factory=list)
