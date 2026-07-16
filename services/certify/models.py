"""Certify models — Pydantic definitions for compliance cards and production certification."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CertificationResult(BaseModel):
    """Compliance metrics and certificate reports generated after certification."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    compliant_controls: list[str] = Field(default_factory=list)
    non_compliant_controls: list[str] = Field(default_factory=list)
    production_cert: str = ""
    deployment_cert: str = ""
    release_cert: str = ""
    security_cert: str = ""
    arch_compliance_report: str = ""
    is_certified: bool = True
