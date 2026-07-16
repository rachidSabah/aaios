"""AAiOS v5.3.2 — Installer package.

Enterprise installation, bootstrap, and configuration for AAiOS.

Modules:
  - models: dataclasses for environment, dependencies, workspace, etc.
  - environment: Phase 1 — EnvironmentDetector
  - dependencies: Phase 2 — DependencyChecker
  - workspace: Phase 3 — WorkspaceBootstrapper
  - database: Phase 4 — DatabaseBootstrapper
  - configuration: Phase 5 — ConfigurationWizard
  - providers: Phase 6 — ProviderConfigurator
  - agents: Phase 7 — AgentBootstrapper
  - orchestrator: InstallerOrchestrator facade

Design principles:
  - Idempotent
  - Restart-safe
  - Transactional
  - Rollback capable
  - Offline aware
  - Online aware
  - Enterprise grade
  - Production ready
  - Fully observable
  - Fully logged
  - Self-documenting

Never destroys user data.
Never overwrites existing configuration without confirmation.
Always creates restore points before making changes.
"""

from __future__ import annotations

from services.installer.agents import (
    SUPPORTED_AGENTS,
    AgentBootstrapper,
    AgentDiscoveryResult,
)
from services.installer.configuration import DEFAULT_PORTS, ConfigurationWizard
from services.installer.database import (
    DEFAULT_DATABASES,
    DatabaseBootstrapper,
)
from services.installer.dependencies import (
    DependencyChecker,
    DependencyRegistry,
    DependencySpec,
)
from services.installer.environment import EnvironmentDetector
from services.installer.models import (
    CompatibilityReport,
    ConfigProfile,
    DependencyCheck,
    DependencyStatus,
    EnvironmentReport,
    InstallationMode,
    InstallationPlan,
    InstallationReport,
    InstallationStage,
    InstallationStep,
    PlatformSupport,
    ProviderCheck,
    RiskLevel,
    RiskReport,
    WorkspaceLayout,
)
from services.installer.orchestrator import InstallerOrchestrator
from services.installer.providers import (
    SUPPORTED_PROVIDERS,
    ProviderConfigurator,
)
from services.installer.workspace import (
    DEFAULT_WORKSPACE_DIRS,
    WorkspaceBootstrapper,
)

__all__ = [
    "AgentBootstrapper",
    "AgentDiscoveryResult",
    "CompatibilityReport",
    "ConfigProfile",
    "DEFAULT_DATABASES",
    "DEFAULT_PORTS",
    "DEFAULT_WORKSPACE_DIRS",
    "DependencyCheck",
    "DependencyChecker",
    "DependencyRegistry",
    "DependencySpec",
    "DependencyStatus",
    "EnvironmentDetector",
    "EnvironmentReport",
    "InstallationMode",
    "InstallationPlan",
    "InstallationReport",
    "InstallationStage",
    "InstallationStep",
    "InstallerOrchestrator",
    "PlatformSupport",
    "ProviderCheck",
    "ProviderConfigurator",
    "RiskLevel",
    "RiskReport",
    "SUPPORTED_AGENTS",
    "SUPPORTED_PROVIDERS",
    "WorkspaceBootstrapper",
    "WorkspaceLayout",
    "ConfigurationWizard",
    "DatabaseBootstrapper",
]
