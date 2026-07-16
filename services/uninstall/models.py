"""Uninstall models — Pydantic definitions for the enterprise uninstallation process."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UninstallConfig(BaseModel):
    """Configuration options for uninstallation."""

    silent: bool = False
    force: bool = False
    keep_data: bool = True
    remove_data: bool = False
    remove_models: bool = False
    remove_providers: bool = False
    remove_plugins: bool = False
    remove_agents: bool = False
    remove_backups: bool = False
    remove_cache: bool = False
    remove_logs: bool = False
    everything: bool = False


class UninstallReport(BaseModel):
    """Report generated after uninstall execution."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stopped_services: list[str] = Field(default_factory=list)
    terminated_processes: list[str] = Field(default_factory=list)
    removed_paths: list[str] = Field(default_factory=list)
    removed_env_vars: list[str] = Field(default_factory=list)
    success: bool = True
    error: str | None = None
