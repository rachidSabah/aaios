"""Doctor models — Pydantic definitions for the diagnostic system."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ScanType(StrEnum):
    """Supported scan types for the enterprise doctor."""

    QUICK = "quick"
    FULL = "full"
    OFFLINE = "offline"
    ONLINE = "online"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    PERFORMANCE = "performance"
    MEMORY = "memory"
    STORAGE = "storage"
    PROVIDER = "provider"
    AGENT = "agent"
    PLUGIN = "plugin"
    MCP = "mcp"
    DATABASE = "database"
    DASHBOARD = "dashboard"
    API = "api"
    CLI = "cli"
    MISSION = "mission"
    WORKFLOW = "workflow"
    GRAPH = "graph"
    VECTOR = "vector"
    CONFIG = "config"
    AUDIT = "audit"
    NETWORK = "network"
    WINDOWS = "windows"


class IssueSeverity(StrEnum):
    """Diagnostic issue severity level."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class DoctorIssue(BaseModel):
    """A single diagnostic issue found during a scan."""

    id: str
    scan_type: ScanType
    severity: IssueSeverity
    description: str
    evidence: str
    root_cause: str
    recommended_fix: str
    repair_available: bool = False


def _get_utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class DoctorReport(BaseModel):
    """Complete enterprise diagnostic report."""

    timestamp: datetime = Field(default_factory=_get_utc_now)
    scan_type: ScanType
    health_score: int = 100
    production_score: int = 100
    risk_score: int = 0
    dependency_score: int = 100
    security_score: int = 100
    performance_score: int = 100
    availability_score: int = 100
    issues: list[DoctorIssue] = Field(default_factory=list)
    scanned_components: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
