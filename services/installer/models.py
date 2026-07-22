"""AAiOS v5.3.2 — Installer models.

Immutable dataclasses for environment discovery, dependency checks,
workspace layout, installation plans, configuration profiles, and
installation reports.

Every model has ``to_dict()`` for JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = [
    "CompatibilityReport",
    "ConfigProfile",
    "DependencyCheck",
    "DependencyStatus",
    "EnvironmentReport",
    "InstallationMode",
    "InstallationPlan",
    "InstallationReport",
    "InstallationStage",
    "InstallationStep",
    "PlatformSupport",
    "ProviderCheck",
    "RiskLevel",
    "RiskReport",
    "WorkspaceLayout",
]


class InstallationMode(StrEnum):
    """Installation mode (selects what to install and how)."""

    INTERACTIVE = "interactive"
    SILENT = "silent"
    MINIMAL = "minimal"
    DEVELOPER = "developer"
    ENTERPRISE = "enterprise"
    PORTABLE = "portable"
    OFFLINE = "offline"
    REPAIR = "repair"
    FORCE = "force"
    UPGRADE = "upgrade"
    VALIDATE = "validate"


class DependencyStatus(StrEnum):
    """Status of a single dependency check."""

    PRESENT = "present"
    MISSING = "missing"
    OUTDATED = "outdated"
    UNSUPPORTED = "unsupported"
    OPTIONAL_SKIPPED = "optional_skipped"
    INSTALL_FAILED = "install_failed"
    INSTALLING = "installing"
    INSTALLED = "installed"


class PlatformSupport(StrEnum):
    """Platform support tier."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


class RiskLevel(StrEnum):
    """Risk levels for the risk report."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfigProfile(StrEnum):
    """Configuration profiles for the wizard."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    ENTERPRISE = "enterprise"
    MINIMAL = "minimal"
    PORTABLE = "portable"


class InstallationStage(StrEnum):
    """Stages of an installation."""

    ENVIRONMENT_DISCOVERY = "environment_discovery"
    DEPENDENCY_DISCOVERY = "dependency_discovery"
    WORKSPACE_BOOTSTRAP = "workspace_bootstrap"
    DATABASE_BOOTSTRAP = "database_bootstrap"
    CONFIGURATION = "configuration"
    PROVIDER_CONFIGURATION = "provider_configuration"
    AGENT_BOOTSTRAP = "agent_bootstrap"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# ---------------------------------------------------------------------------
# Phase 1 — Environment discovery
# ---------------------------------------------------------------------------


@dataclass
class EnvironmentReport:
    """Phase 1 — full environment report.

    Captures OS, hardware, network, security software, and tool versions
    detected on the host. Populated by ``EnvironmentDetector``.
    """

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # OS
    os_name: str = ""
    os_version: str = ""
    os_build: str = ""
    platform_support: str = PlatformSupport.UNSUPPORTED.value

    # Hardware
    cpu_arch: str = ""
    cpu_count: int = 0
    cpu_brand: str = ""
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu: list[str] = field(default_factory=list)
    cuda_available: bool = False
    cuda_version: str = ""
    disk_total_gb: float = 0.0
    disk_available_gb: float = 0.0

    # Network
    internet_connected: bool = False
    internet_latency_ms: float = 0.0
    corporate_proxy: str = ""
    firewall_detected: bool = False

    # Privileges & security
    is_administrator: bool = False
    powershell_version: str = ""
    antivirus: list[str] = field(default_factory=list)
    windows_defender_active: bool = False

    # Tools
    python_version: str = ""
    python_path: str = ""
    node_version: str = ""
    node_path: str = ""
    git_version: str = ""
    git_path: str = ""
    docker_version: str = ""
    docker_path: str = ""
    wsl_available: bool = False
    wsl_version: str = ""
    hyperv_available: bool = False
    is_virtual_machine: bool = False

    # Locale
    filesystem: str = ""
    locale: str = ""
    timezone: str = ""

    # PATH
    path_entries: list[str] = field(default_factory=list)
    path_issues: list[str] = field(default_factory=list)

    # Errors during detection
    detection_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "detected_at": self.detected_at.isoformat(),
            "os_name": self.os_name,
            "os_version": self.os_version,
            "os_build": self.os_build,
            "platform_support": self.platform_support,
            "cpu_arch": self.cpu_arch,
            "cpu_count": self.cpu_count,
            "cpu_brand": self.cpu_brand,
            "ram_total_gb": round(self.ram_total_gb, 2),
            "ram_available_gb": round(self.ram_available_gb, 2),
            "gpu": list(self.gpu),
            "cuda_available": self.cuda_available,
            "cuda_version": self.cuda_version,
            "disk_total_gb": round(self.disk_total_gb, 2),
            "disk_available_gb": round(self.disk_available_gb, 2),
            "internet_connected": self.internet_connected,
            "internet_latency_ms": round(self.internet_latency_ms, 2),
            "corporate_proxy": self.corporate_proxy,
            "firewall_detected": self.firewall_detected,
            "is_administrator": self.is_administrator,
            "powershell_version": self.powershell_version,
            "antivirus": list(self.antivirus),
            "windows_defender_active": self.windows_defender_active,
            "python_version": self.python_version,
            "python_path": self.python_path,
            "node_version": self.node_version,
            "node_path": self.node_path,
            "git_version": self.git_version,
            "git_path": self.git_path,
            "docker_version": self.docker_version,
            "docker_path": self.docker_path,
            "wsl_available": self.wsl_available,
            "wsl_version": self.wsl_version,
            "hyperv_available": self.hyperv_available,
            "is_virtual_machine": self.is_virtual_machine,
            "filesystem": self.filesystem,
            "locale": self.locale,
            "timezone": self.timezone,
            "path_entries": list(self.path_entries),
            "path_issues": list(self.path_issues),
            "detection_errors": list(self.detection_errors),
        }


@dataclass
class CompatibilityReport:
    """Phase 1 — compatibility assessment."""

    compatible: bool = False
    platform_support: str = PlatformSupport.UNSUPPORTED.value
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    python_compatible: bool = False
    ram_sufficient: bool = False
    disk_sufficient: bool = False
    network_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "platform_support": self.platform_support,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "python_compatible": self.python_compatible,
            "ram_sufficient": self.ram_sufficient,
            "disk_sufficient": self.disk_sufficient,
            "network_available": self.network_available,
        }


@dataclass
class InstallationStep:
    """A single step in the installation plan."""

    step_id: str = field(default_factory=lambda: uuid4().hex[:8])
    stage: str = ""
    name: str = ""
    description: str = ""
    required: bool = True
    estimated_seconds: float = 0.0
    dependencies: list[str] = field(default_factory=list)
    can_skip: bool = False
    can_rollback: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "stage": self.stage,
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "estimated_seconds": round(self.estimated_seconds, 2),
            "dependencies": list(self.dependencies),
            "can_skip": self.can_skip,
            "can_rollback": self.can_rollback,
        }


@dataclass
class InstallationPlan:
    """Phase 1 — installation plan derived from environment + mode."""

    plan_id: str = field(default_factory=lambda: uuid4().hex[:12])
    mode: str = InstallationMode.INTERACTIVE.value
    steps: list[InstallationStep] = field(default_factory=list)
    total_estimated_seconds: float = 0.0
    workspace_root: str = ""
    profile: str = ConfigProfile.DEVELOPMENT.value
    requires_reboot: bool = False
    requires_admin: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "mode": self.mode,
            "steps": [s.to_dict() for s in self.steps],
            "total_estimated_seconds": round(self.total_estimated_seconds, 2),
            "workspace_root": self.workspace_root,
            "profile": self.profile,
            "requires_reboot": self.requires_reboot,
            "requires_admin": self.requires_admin,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RiskReport:
    """Phase 1 — risk assessment."""

    overall_risk: str = RiskLevel.INFO.value
    risks: list[dict[str, Any]] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_risk": self.overall_risk,
            "risks": list(self.risks),
            "mitigations": list(self.mitigations),
        }


# ---------------------------------------------------------------------------
# Phase 2 — Dependency discovery
# ---------------------------------------------------------------------------


@dataclass
class DependencyCheck:
    """Phase 2 — a single dependency check result."""

    name: str = ""
    category: str = ""  # required | optional | recommended
    status: str = DependencyStatus.MISSING.value
    detected_version: str = ""
    required_version: str = ""
    install_path: str = ""
    in_path: bool = False
    license: str = ""
    healthy: bool = False
    health_check_output: str = ""
    install_attempted: bool = False
    install_succeeded: bool = False
    error: str | None = None
    can_install: bool = True
    can_skip: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "detected_version": self.detected_version,
            "required_version": self.required_version,
            "install_path": self.install_path,
            "in_path": self.in_path,
            "license": self.license,
            "healthy": self.healthy,
            "health_check_output": self.health_check_output,
            "install_attempted": self.install_attempted,
            "install_succeeded": self.install_succeeded,
            "error": self.error,
            "can_install": self.can_install,
            "can_skip": self.can_skip,
        }


# ---------------------------------------------------------------------------
# Phase 3 — Workspace layout
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceLayout:
    """Phase 3 — workspace directory layout."""

    root: str = ""
    created_dirs: list[str] = field(default_factory=list)
    skipped_dirs: list[str] = field(default_factory=list)
    failed_dirs: list[str] = field(default_factory=list)
    existing_dirs: list[str] = field(default_factory=list)
    total_size_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "created_dirs": list(self.created_dirs),
            "skipped_dirs": list(self.skipped_dirs),
            "failed_dirs": list(self.failed_dirs),
            "existing_dirs": list(self.existing_dirs),
            "total_size_mb": round(self.total_size_mb, 2),
        }


# ---------------------------------------------------------------------------
# Phase 4 — Database bootstrap
# ---------------------------------------------------------------------------


@dataclass
class DatabaseBootstrapResult:
    """Phase 4 — result of bootstrapping a single database."""

    name: str = ""
    backend: str = ""  # sqlite | postgres | qdrant | memory
    status: str = "pending"  # pending | migrated | verified | failed | skipped
    schema_created: bool = False
    migrations_applied: int = 0
    migrations_rolled_back: int = 0
    integrity_ok: bool = False
    backup_path: str = ""
    error: str | None = None
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "backend": self.backend,
            "status": self.status,
            "schema_created": self.schema_created,
            "migrations_applied": self.migrations_applied,
            "migrations_rolled_back": self.migrations_rolled_back,
            "integrity_ok": self.integrity_ok,
            "backup_path": self.backup_path,
            "error": self.error,
            "duration_s": round(self.duration_s, 2),
        }


# ---------------------------------------------------------------------------
# Phase 5 — Configuration wizard
# ---------------------------------------------------------------------------


@dataclass
class ConfigurationSpec:
    """Phase 5 — a complete configuration spec."""

    profile: str = ConfigProfile.DEVELOPMENT.value
    workspace_root: str = ""
    storage: dict[str, Any] = field(default_factory=dict)
    ports: dict[str, int] = field(default_factory=dict)
    providers: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    databases: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    knowledge_graph: dict[str, Any] = field(default_factory=dict)
    plugins: list[str] = field(default_factory=list)
    mcp: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    authentication: dict[str, Any] = field(default_factory=dict)
    rbac: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)
    dashboard: dict[str, Any] = field(default_factory=dict)
    api: dict[str, Any] = field(default_factory=dict)
    cli: dict[str, Any] = field(default_factory=dict)
    update_policy: dict[str, Any] = field(default_factory=dict)
    backup_policy: dict[str, Any] = field(default_factory=dict)
    recovery_policy: dict[str, Any] = field(default_factory=dict)
    performance_profile: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "workspace_root": self.workspace_root,
            "storage": dict(self.storage),
            "ports": dict(self.ports),
            "providers": list(self.providers),
            "models": list(self.models),
            "databases": dict(self.databases),
            "memory": dict(self.memory),
            "knowledge_graph": dict(self.knowledge_graph),
            "plugins": list(self.plugins),
            "mcp": dict(self.mcp),
            "security": dict(self.security),
            "authentication": dict(self.authentication),
            "rbac": dict(self.rbac),
            "logging": dict(self.logging),
            "telemetry": dict(self.telemetry),
            "dashboard": dict(self.dashboard),
            "api": dict(self.api),
            "cli": dict(self.cli),
            "update_policy": dict(self.update_policy),
            "backup_policy": dict(self.backup_policy),
            "recovery_policy": dict(self.recovery_policy),
            "performance_profile": dict(self.performance_profile),
        }


# ---------------------------------------------------------------------------
# Phase 6 — Provider configuration
# ---------------------------------------------------------------------------


@dataclass
class ProviderCheck:
    """Phase 6 — result of a single provider check."""

    name: str = ""
    configured: bool = False
    enabled: bool = False
    healthy: bool = False
    models_discovered: list[str] = field(default_factory=list)
    supports_streaming: bool = False
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    fallback_priority: int = 0
    error: str | None = None
    health_check_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "configured": self.configured,
            "enabled": self.enabled,
            "healthy": self.healthy,
            "models_discovered": list(self.models_discovered),
            "supports_streaming": self.supports_streaming,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "supports_reasoning": self.supports_reasoning,
            "fallback_priority": self.fallback_priority,
            "error": self.error,
            "health_check_latency_ms": round(self.health_check_latency_ms, 2),
        }


# ---------------------------------------------------------------------------
# Final installation report
# ---------------------------------------------------------------------------


@dataclass
class InstallationReport:
    """Top-level installation report covering all phases."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    mode: str = InstallationMode.INTERACTIVE.value
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    current_stage: str = InstallationStage.ENVIRONMENT_DISCOVERY.value
    overall_status: str = "running"  # running | success | partial | failed | rolled_back
    environment: EnvironmentReport | None = None
    compatibility: CompatibilityReport | None = None
    plan: InstallationPlan | None = None
    risks: RiskReport | None = None
    dependencies: list[DependencyCheck] = field(default_factory=list)
    workspace: WorkspaceLayout | None = None
    databases: list[DatabaseBootstrapResult] = field(default_factory=list)
    configuration: ConfigurationSpec | None = None
    providers: list[ProviderCheck] = field(default_factory=list)
    agents_registered: list[str] = field(default_factory=list)
    restore_point_path: str = ""
    log_path: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "mode": self.mode,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_stage": self.current_stage,
            "overall_status": self.overall_status,
            "environment": self.environment.to_dict() if self.environment else None,
            "compatibility": self.compatibility.to_dict() if self.compatibility else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "risks": self.risks.to_dict() if self.risks else None,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "workspace": self.workspace.to_dict() if self.workspace else None,
            "databases": [d.to_dict() for d in self.databases],
            "configuration": self.configuration.to_dict() if self.configuration else None,
            "providers": [p.to_dict() for p in self.providers],
            "agents_registered": list(self.agents_registered),
            "restore_point_path": self.restore_point_path,
            "log_path": self.log_path,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
