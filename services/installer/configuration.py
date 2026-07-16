"""Phase 5 — Configuration Wizard.

Generates a complete configuration spec for AAiOS. Supports two modes:

  - Interactive: prompts the user for each choice (delegated to the CLI)
  - Silent: applies a profile-based default with no prompts

Profiles:
  - development: permissive defaults, debug logging, no auth
  - production: secure defaults, info logging, RBAC on
  - enterprise: strict defaults, audit everything, RBAC + auth + telemetry
  - minimal: only required subsystems
  - portable: self-contained, no system services
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.installer.models import ConfigProfile, ConfigurationSpec
from services.installer.workspace import WorkspaceBootstrapper

_log = get_logger(__name__)

__all__ = ["ConfigurationWizard", "DEFAULT_PORTS"]


DEFAULT_PORTS: dict[str, int] = {
    "api": 8000,
    "dashboard": 3000,
    "postgres": 5432,
    "qdrant": 6333,
    "redis": 6379,
    "ollama": 11434,
    "lm_studio": 1234,
}


# Profile defaults
_PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    ConfigProfile.DEVELOPMENT.value: {
        "logging_level": "DEBUG",
        "telemetry_enabled": False,
        "auth_required": False,
        "rbac_required": False,
        "audit_enabled": True,
        "auto_update": True,
        "backup_interval_hours": 0,  # disabled
        "dashboard_enabled": True,
        "api_cors_origins": ["*"],
    },
    ConfigProfile.PRODUCTION.value: {
        "logging_level": "INFO",
        "telemetry_enabled": True,
        "auth_required": True,
        "rbac_required": True,
        "audit_enabled": True,
        "auto_update": False,
        "backup_interval_hours": 24,
        "dashboard_enabled": True,
        "api_cors_origins": [],  # must be set explicitly
    },
    ConfigProfile.ENTERPRISE.value: {
        "logging_level": "INFO",
        "telemetry_enabled": True,
        "auth_required": True,
        "rbac_required": True,
        "audit_enabled": True,
        "auto_update": False,
        "backup_interval_hours": 6,
        "dashboard_enabled": True,
        "api_cors_origins": [],
        "strict_mode": True,
        "encrypted_secrets": True,
        "ssl_required": True,
    },
    ConfigProfile.MINIMAL.value: {
        "logging_level": "WARNING",
        "telemetry_enabled": False,
        "auth_required": False,
        "rbac_required": False,
        "audit_enabled": False,
        "auto_update": False,
        "backup_interval_hours": 0,
        "dashboard_enabled": False,
        "api_cors_origins": [],
    },
    ConfigProfile.PORTABLE.value: {
        "logging_level": "INFO",
        "telemetry_enabled": False,
        "auth_required": False,
        "rbac_required": False,
        "audit_enabled": True,
        "auto_update": False,
        "backup_interval_hours": 0,
        "dashboard_enabled": True,
        "api_cors_origins": ["*"],
        "portable_mode": True,
    },
}


class ConfigurationWizard:
    """Phase 5 — generate a configuration spec.

    The wizard is non-interactive by default. To run interactively, the
    CLI passes ``interactive=True`` and the wizard returns prompts that
    the CLI renders. The wizard itself never reads stdin directly —
    this keeps it testable.
    """

    def __init__(self, workspace: WorkspaceBootstrapper) -> None:
        self._workspace = workspace

    def generate(
        self,
        profile: ConfigProfile | str = ConfigProfile.DEVELOPMENT,
        *,
        interactive: bool = False,
        overrides: dict[str, Any] | None = None,
    ) -> ConfigurationSpec:
        """Generate a configuration spec.

        Args:
            profile: configuration profile to apply.
            interactive: if True, the wizard returns a spec with
                ``_prompts`` filled in (the CLI renders them).
            overrides: per-key overrides applied on top of the profile defaults.
        """
        p = ConfigProfile(profile) if isinstance(profile, str) else profile
        defaults = dict(_PROFILE_DEFAULTS.get(p.value, {}))
        if overrides:
            defaults.update(overrides)
        spec = ConfigurationSpec(
            profile=p.value,
            workspace_root=str(self._workspace.root),
            storage=self._storage_config(defaults),
            ports=dict(DEFAULT_PORTS),
            providers=self._providers_config(defaults),
            models=self._models_config(defaults),
            databases=self._databases_config(defaults),
            memory=self._memory_config(defaults),
            knowledge_graph=self._knowledge_graph_config(defaults),
            plugins=self._plugins_config(defaults),
            mcp=self._mcp_config(defaults),
            security=self._security_config(defaults),
            authentication=self._auth_config(defaults),
            rbac=self._rbac_config(defaults),
            logging=self._logging_config(defaults),
            telemetry=self._telemetry_config(defaults),
            dashboard=self._dashboard_config(defaults),
            api=self._api_config(defaults),
            cli=self._cli_config(defaults),
            update_policy=self._update_policy(defaults),
            backup_policy=self._backup_policy(defaults),
            recovery_policy=self._recovery_policy(defaults),
            performance_profile=self._performance_config(defaults),
        )
        if interactive:
            spec.performance_profile["_prompts"] = self._build_prompts(spec)
        return spec

    def save(self, spec: ConfigurationSpec, filename: str = "config.json") -> Path:
        """Save the configuration spec to the workspace ``config/`` directory."""
        config_dir = self._workspace.ensure_dir("config")
        path = config_dir / filename
        path.write_text(json.dumps(spec.to_dict(), indent=2, default=str))
        _log.info("installer.config_saved", path=str(path))
        return path

    def load(self, filename: str = "config.json") -> ConfigurationSpec | None:
        """Load a saved configuration spec."""
        path = self._workspace.path_for("config", filename)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return ConfigurationSpec(
                profile=data.get("profile", ConfigProfile.DEVELOPMENT.value),
                workspace_root=data.get("workspace_root", str(self._workspace.root)),
                storage=data.get("storage", {}),
                ports=data.get("ports", {}),
                providers=data.get("providers", []),
                models=data.get("models", []),
                databases=data.get("databases", {}),
                memory=data.get("memory", {}),
                knowledge_graph=data.get("knowledge_graph", {}),
                plugins=data.get("plugins", []),
                mcp=data.get("mcp", {}),
                security=data.get("security", {}),
                authentication=data.get("authentication", {}),
                rbac=data.get("rbac", {}),
                logging=data.get("logging", {}),
                telemetry=data.get("telemetry", {}),
                dashboard=data.get("dashboard", {}),
                api=data.get("api", {}),
                cli=data.get("cli", {}),
                update_policy=data.get("update_policy", {}),
                backup_policy=data.get("backup_policy", {}),
                recovery_policy=data.get("recovery_policy", {}),
                performance_profile=data.get("performance_profile", {}),
            )
        except (json.JSONDecodeError, OSError) as e:
            _log.warning("installer.config_load_failed", error=str(e))
            return None

    # --- config builders -----------------------------------------------

    def _storage_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "workspace_root": str(self._workspace.root),
            "database_dir": str(self._workspace.path_for("database")),
            "memory_dir": str(self._workspace.path_for("memory")),
            "knowledge_graph_dir": str(self._workspace.path_for("knowledge-graph")),
            "vector_storage_dir": str(self._workspace.path_for("vector-storage")),
            "backups_dir": str(self._workspace.path_for("backups")),
            "cache_dir": str(self._workspace.path_for("caches")),
        }

    def _providers_config(self, d: dict[str, Any]) -> list[str]:
        # Return list of providers to enable by default
        if d.get("strict_mode"):
            return []  # enterprise: must be configured explicitly
        return ["ollama", "lm-studio"]  # local-only by default

    def _models_config(self, d: dict[str, Any]) -> list[str]:
        return ["default"]

    def _databases_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "primary": "sqlite",
            "sqlite_path": str(self._workspace.path_for("database", "aaios.db")),
            "postgres_url": "",
            "qdrant_url": "",
            "redis_url": "",
        }

    def _memory_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "backend": "sqlite",
            "scopes": ["short_term", "long_term", "episodic", "semantic"],
            "compression_threshold": 1024,
        }

    def _knowledge_graph_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "backend": "sqlite",
            "node_types": ["claim", "fact", "source", "document", "report", "session"],
            "edge_types": ["support", "contradiction", "dependency", "reference", "citation"],
        }

    def _plugins_config(self, d: dict[str, Any]) -> list[str]:
        return []

    def _mcp_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": True,
            "servers": [],
        }

    def _security_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "audit_enabled": d.get("audit_enabled", True),
            "encrypted_secrets": d.get("encrypted_secrets", False),
            "ssl_required": d.get("ssl_required", False),
            "strict_mode": d.get("strict_mode", False),
            "sandbox_enabled": True,
        }

    def _auth_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "required": d.get("auth_required", False),
            "method": "token",  # token | oauth | saml
            "token_expiry_hours": 24,
            "min_password_length": 12 if d.get("strict_mode") else 8,
        }

    def _rbac_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "required": d.get("rbac_required", False),
            "roles": ["admin", "operator", "viewer", "owner"],
            "default_role": "viewer",
        }

    def _logging_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "level": d.get("logging_level", "INFO"),
            "format": "json",
            "destination": "both",  # file | console | both
            "file_path": str(self._workspace.path_for("logs", "aaios.log")),
            "rotation_size_mb": 100,
            "retention_days": 30,
        }

    def _telemetry_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": d.get("telemetry_enabled", False),
            "endpoint": "",
            "sample_rate": 0.1,
            "trace_enabled": True,
            "metrics_enabled": True,
        }

    def _dashboard_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": d.get("dashboard_enabled", True),
            "port": DEFAULT_PORTS["dashboard"],
            "host": "127.0.0.1",
        }

    def _api_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "port": DEFAULT_PORTS["api"],
            "host": "127.0.0.1",
            "cors_origins": d.get("api_cors_origins", []),
            "rate_limit_per_minute": 60 if d.get("strict_mode") else 600,
            "auth_required": d.get("auth_required", False),
        }

    def _cli_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "color_enabled": True,
            "pager_enabled": True,
            "default_format": "table",
            "api_url": f"http://127.0.0.1:{DEFAULT_PORTS['api']}",
        }

    def _update_policy(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "auto_update": d.get("auto_update", False),
            "channel": "stable",
            "check_interval_hours": 24,
            "notify_only": not d.get("auto_update", False),
        }

    def _backup_policy(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "interval_hours": d.get("backup_interval_hours", 24),
            "retention_count": 10,
            "destination": str(self._workspace.path_for("backups")),
            "include_databases": True,
            "include_config": True,
            "include_logs": False,
        }

    def _recovery_policy(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "auto_recover": True,
            "max_retries": 3,
            "rollback_on_failure": True,
            "notify_on_recovery": True,
        }

    def _performance_config(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            "worker_processes": 4,
            "max_concurrent_agents": 8,
            "memory_limit_mb": 2048,
            "cache_enabled": True,
            "cache_size_mb": 256,
            "portable_mode": d.get("portable_mode", False),
            "strict_mode": d.get("strict_mode", False),
        }

    def _build_prompts(self, spec: ConfigurationSpec) -> list[dict[str, Any]]:
        """Build the list of interactive prompts for the CLI to render."""
        return [
            {
                "id": "profile",
                "question": "Configuration profile",
                "default": spec.profile,
                "options": [p.value for p in ConfigProfile],
            },
            {
                "id": "workspace_root",
                "question": "Workspace root",
                "default": spec.workspace_root,
            },
            {
                "id": "api_port",
                "question": "API port",
                "default": spec.ports.get("api", 8000),
            },
            {
                "id": "dashboard_port",
                "question": "Dashboard port",
                "default": spec.ports.get("dashboard", 3000),
            },
            {
                "id": "logging_level",
                "question": "Logging level",
                "default": spec.logging.get("level", "INFO"),
                "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
            },
            {
                "id": "auth_required",
                "question": "Require authentication?",
                "default": spec.authentication.get("required", False),
                "options": [True, False],
            },
            {
                "id": "auto_update",
                "question": "Enable auto-update?",
                "default": spec.update_policy.get("auto_update", False),
                "options": [True, False],
            },
            {
                "id": "backup_interval",
                "question": "Backup interval (hours, 0=disabled)",
                "default": spec.backup_policy.get("interval_hours", 24),
            },
        ]
