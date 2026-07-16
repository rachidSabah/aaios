"""Packaging models — Pydantic definitions for release packaging and metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PackageType(StrEnum):
    """Supported production package types."""

    PORTABLE = "portable"
    ZIP = "zip"
    INSTALLER = "installer"
    OFFLINE_INSTALLER = "offline_installer"
    DEVELOPER = "developer"
    ENTERPRISE = "enterprise"


class PackageMetadata(BaseModel):
    """Metadata for a single package artifact."""

    id: str
    filename: str
    package_type: PackageType
    size_bytes: int
    sha256: str
    sha512: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReleaseManifest(BaseModel):
    """Release manifest bundling all compiled packages and licenses."""

    version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    packages: list[PackageMetadata] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(default_factory=dict)
    licenses: dict[str, str] = Field(default_factory=dict)
    sbom: dict[str, Any] = Field(default_factory=dict)
