"""Validation models — Pydantic definitions for release validation and compliance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ValidationReport(BaseModel):
    """Result of running aaios validate command."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    success: bool = True
    checked_stages: list[str] = Field(default_factory=list)
    static_analysis_ok: bool = True
    runtime_ok: bool = True
    dependencies_ok: bool = True
    providers_ok: bool = True
    plugins_ok: bool = True
    mcp_ok: bool = True
    database_ok: bool = True
    performance_ok: bool = True
    security_ok: bool = True
    memory_ok: bool = True
    mission_ok: bool = True
    workflow_ok: bool = True
    dashboard_ok: bool = True
    api_ok: bool = True
    cli_ok: bool = True
    errors: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class CertificationReport(BaseModel):
    """Formal compliance certification report for AAiOS."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    certification_id: str = Field(
        default_factory=lambda: f"CERT-{int(datetime.now(UTC).timestamp())}"
    )
    compliance_level: str = "Enterprise Grade"
    checked_controls: int = 0
    passed_controls: int = 0
    status: str = "certified"
    notes: str = ""


class DeploymentReadinessReport(BaseModel):
    """Assessment of deployment readiness prior to production push."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    readiness_score: int = 100
    is_ready: bool = True
    blockers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
