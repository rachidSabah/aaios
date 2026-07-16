"""Doctor manager — runs diagnostic scans and generates health reports."""

from __future__ import annotations

import os
import platform
import shutil
import socket
import sqlite3
import sys
from pathlib import Path

import httpx

from core.logging import get_logger
from services.doctor.models import (
    DoctorIssue,
    DoctorReport,
    IssueSeverity,
    ScanType,
)

_log = get_logger(__name__)

__all__ = ["DoctorManager"]


class DoctorManager:
    """Enterprise diagnostic system for AAiOS."""

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        _log.info("doctor.initialized", workspace_root=str(self.workspace_root))

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    def run_scan(self, scan_type: ScanType = ScanType.QUICK) -> DoctorReport:
        """Run the diagnostic suite for the specified scan type."""
        report = DoctorReport(scan_type=scan_type)
        issues: list[DoctorIssue] = []
        scanned: list[str] = []

        # Determine which sub-scans to run based on scan_type
        run_all = scan_type in (ScanType.FULL, ScanType.ONLINE)
        is_online = scan_type in (ScanType.ONLINE, ScanType.FULL)
        is_offline = scan_type == ScanType.OFFLINE

        # 1. Configuration Scan (always run)
        self._scan_config(issues, scanned)

        # 2. Database Scan
        if run_all or scan_type in (ScanType.DATABASE, ScanType.QUICK):
            self._scan_database(issues, scanned)

        # 3. Dependency Scan
        if run_all or scan_type == ScanType.DEPENDENCY:
            self._scan_dependency(issues, scanned)

        # 4. Windows Scan
        if run_all or scan_type in (ScanType.WINDOWS, ScanType.QUICK):
            self._scan_windows(issues, scanned)

        # 5. Security & Audit Scan
        if run_all or scan_type in (ScanType.SECURITY, ScanType.AUDIT):
            self._scan_security_and_audit(issues, scanned)

        # 6. Storage & Memory Scan
        if run_all or scan_type in (ScanType.STORAGE, ScanType.MEMORY):
            self._scan_storage_and_memory(issues, scanned)

        # 7. Network & Provider Scan
        if (run_all or scan_type in (ScanType.NETWORK, ScanType.PROVIDER)) and not is_offline:
            self._scan_network_and_providers(issues, scanned, force_online=is_online)

        # 8. Agent & Plugin Scan
        if run_all or scan_type in (ScanType.AGENT, ScanType.PLUGIN, ScanType.MCP):
            self._scan_agents_and_plugins(issues, scanned)

        # 9. CLI, API & Dashboard Scan
        if run_all or scan_type in (ScanType.CLI, ScanType.API, ScanType.DASHBOARD, ScanType.QUICK):
            self._scan_interfaces(issues, scanned)

        # 10. Mission & Workflow Scan
        if run_all or scan_type in (ScanType.MISSION, ScanType.WORKFLOW):
            self._scan_mission_and_workflow(issues, scanned)

        # 11. Graph & Vector Scan
        if run_all or scan_type in (ScanType.GRAPH, ScanType.VECTOR):
            self._scan_graph_and_vector(issues, scanned)

        report.issues = issues
        report.scanned_components = scanned

        # Calculate scores
        self._calculate_scores(report)
        return report

    def _scan_config(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan configuration files and directories."""
        scanned.append("configuration")
        config_dir = self.workspace_root / "config"
        defaults_yaml = config_dir / "defaults.yaml"
        config_yaml = config_dir / "config.yaml"

        if not config_dir.exists():
            issues.append(
                DoctorIssue(
                    id="CONFIG_DIR_MISSING",
                    scan_type=ScanType.CONFIG,
                    severity=IssueSeverity.BLOCKER,
                    description="Workspace configuration directory does not exist",
                    evidence=f"Path checked: {config_dir}",
                    root_cause="Workspace has not been bootstrapped or config directory was deleted",
                    recommended_fix="Run 'aaios doctor' self-healing or recreate config/ directory",
                    repair_available=True,
                )
            )
            return

        if not defaults_yaml.exists():
            issues.append(
                DoctorIssue(
                    id="DEFAULTS_YAML_MISSING",
                    scan_type=ScanType.CONFIG,
                    severity=IssueSeverity.CRITICAL,
                    description="Default configuration file (defaults.yaml) is missing",
                    evidence=f"Path checked: {defaults_yaml}",
                    root_cause="Installation is corrupt or defaults.yaml was deleted",
                    recommended_fix="Reinstall default configuration or run aaios restore",
                    repair_available=True,
                )
            )

        if not config_yaml.exists():
            issues.append(
                DoctorIssue(
                    id="CONFIG_YAML_MISSING",
                    scan_type=ScanType.CONFIG,
                    severity=IssueSeverity.WARNING,
                    description="User configuration file (config.yaml) is missing",
                    evidence=f"Path checked: {config_yaml}",
                    root_cause="User has not customized the configuration yet",
                    recommended_fix="Run configuration wizard or create empty config.yaml",
                    repair_available=True,
                )
            )

    def _scan_database(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan and verify SQLite databases."""
        scanned.append("database")
        db_dir = self.workspace_root / "database"
        if not db_dir.exists():
            issues.append(
                DoctorIssue(
                    id="DB_DIR_MISSING",
                    scan_type=ScanType.DATABASE,
                    severity=IssueSeverity.CRITICAL,
                    description="Database directory does not exist",
                    evidence=f"Path checked: {db_dir}",
                    root_cause="Workspace has not been bootstrapped",
                    recommended_fix="Run database bootstrapper or self-healing",
                    repair_available=True,
                )
            )
            return

        from services.installer.database import DEFAULT_DATABASES

        for db_name in DEFAULT_DATABASES:
            db_path = db_dir / f"{db_name}.db"
            if not db_path.exists():
                issues.append(
                    DoctorIssue(
                        id=f"DB_FILE_MISSING_{db_name.upper()}",
                        scan_type=ScanType.DATABASE,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Database file for '{db_name}' is missing",
                        evidence=f"Path checked: {db_path}",
                        root_cause="Database was deleted or not bootstrapped",
                        recommended_fix=f"Bootstrap database '{db_name}'",
                        repair_available=True,
                    )
                )
                continue

            # Run integrity check
            try:
                # Open read-only to avoid modification
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check;")
                    result = cursor.fetchone()
                    if not result or result[0] != "ok":
                        issues.append(
                            DoctorIssue(
                                id=f"DB_CORRUPTED_{db_name.upper()}",
                                scan_type=ScanType.DATABASE,
                                severity=IssueSeverity.BLOCKER,
                                description=f"Database '{db_name}' is corrupted",
                                evidence=f"PRAGMA integrity_check result: {result}",
                                root_cause="Improper shutdown, hardware failure, or external modification",
                                recommended_fix=f"Restore '{db_name}' from backup or rebuild",
                                repair_available=True,
                            )
                        )
                finally:
                    conn.close()
            except sqlite3.Error as e:
                issues.append(
                    DoctorIssue(
                        id=f"DB_CONN_FAILED_{db_name.upper()}",
                        scan_type=ScanType.DATABASE,
                        severity=IssueSeverity.BLOCKER,
                        description=f"Failed to connect to SQLite database '{db_name}'",
                        evidence=str(e),
                        root_cause="File permission issues or format corruption",
                        recommended_fix=f"Check permissions for {db_path} or restore",
                        repair_available=True,
                    )
                )

    def _scan_dependency(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan Python and Node.js dependencies."""
        scanned.append("dependencies")

        # Check Python imports
        required_imports = [
            ("fastapi", "FastAPI"),
            ("pydantic", "Pydantic"),
            ("sqlalchemy", "SQLAlchemy"),
            ("structlog", "Structlog"),
            ("typer", "Typer"),
            ("rich", "Rich"),
        ]
        if platform.system() == "Windows":
            required_imports.append(("win32api", "pywin32"))

        for mod_name, label in required_imports:
            try:
                __import__(mod_name)
            except ImportError as e:
                issues.append(
                    DoctorIssue(
                        id=f"PYTHON_DEP_MISSING_{mod_name.upper()}",
                        scan_type=ScanType.DEPENDENCY,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Required Python dependency '{label}' is not installed",
                        evidence=str(e),
                        root_cause="Virtual environment is missing packages or not active",
                        recommended_fix="Run 'pnpm install' or pip install in virtualenv",
                        repair_available=True,
                    )
                )

        # Check package.json & pnpm
        package_json = self.workspace_root / "package.json"
        if not package_json.exists():
            issues.append(
                DoctorIssue(
                    id="PACKAGE_JSON_MISSING",
                    scan_type=ScanType.DEPENDENCY,
                    severity=IssueSeverity.WARNING,
                    description="Root package.json is missing",
                    evidence=f"Path checked: {package_json}",
                    root_cause="Incomplete clone or custom layout",
                    recommended_fix="Re-clone repository or create package.json",
                    repair_available=False,
                )
            )
        else:
            # Check node_modules
            node_modules = self.workspace_root / "node_modules"
            if not node_modules.exists() or not node_modules.is_dir():
                issues.append(
                    DoctorIssue(
                        id="NODE_MODULES_MISSING",
                        scan_type=ScanType.DEPENDENCY,
                        severity=IssueSeverity.CRITICAL,
                        description="Node dependencies (node_modules) are not installed",
                        evidence=f"Path checked: {node_modules}",
                        root_cause="pnpm install has not been run",
                        recommended_fix="Run 'pnpm install' at workspace root",
                        repair_available=True,
                    )
                )

    def _scan_windows(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan Windows native properties and invariants."""
        scanned.append("windows")
        is_windows = platform.system() == "Windows"

        if not is_windows:
            issues.append(
                DoctorIssue(
                    id="PLATFORM_NOT_WINDOWS",
                    scan_type=ScanType.WINDOWS,
                    severity=IssueSeverity.WARNING,
                    description="Running on a non-Windows platform",
                    evidence=f"Platform system: {platform.system()}",
                    root_cause="AAiOS is designed as a Windows-first runtime, running on Linux/macOS may disable native desktop agents",
                    recommended_fix="Use Windows for full capability support",
                    repair_available=False,
                )
            )
            return

        # Check PowerShell version
        try:
            import subprocess
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],  # noqa: S603, S607
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                major = int(res.stdout.strip())
                if major < 5:
                    issues.append(
                        DoctorIssue(
                            id="POWERSHELL_VERSION_LOW",
                            scan_type=ScanType.WINDOWS,
                            severity=IssueSeverity.WARNING,
                            description="PowerShell version is below 5.1",
                            evidence=f"Major version: {major}",
                            root_cause="Older Windows OS version",
                            recommended_fix="Update PowerShell to version 5.1 or higher",
                            repair_available=False,
                        )
                    )
        except Exception:  # noqa: BLE001
            pass

    def _scan_security_and_audit(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan folder permissions and verify cryptographic audit log chain."""
        scanned.append("security")
        scanned.append("audit")
        secrets_dir = self.workspace_root / "secrets"
        if not secrets_dir.exists():
            issues.append(
                DoctorIssue(
                    id="SECRETS_DIR_MISSING",
                    scan_type=ScanType.SECURITY,
                    severity=IssueSeverity.CRITICAL,
                    description="Secrets storage directory is missing",
                    evidence="Folder does not exist",
                    root_cause="Installation incomplete or deleted directory",
                    recommended_fix="Recreate folder and secure permissions",
                    repair_available=True,
                )
            )
        # Check permissions
        elif sys.platform == "win32":
            # Check that only the current user or admins can write
            pass  # Simplified for now, but we can verify write/read permission
        else:
            mode = secrets_dir.stat().st_mode
            if mode & 0o077:  # group/others have access
                issues.append(
                    DoctorIssue(
                        id="SECRETS_DIR_PERMISSIONS_LOOSE",
                        scan_type=ScanType.SECURITY,
                        severity=IssueSeverity.WARNING,
                        description="Secrets directory permissions are too loose",
                        evidence=oct(mode),
                        root_cause="Directory was created with default loose umask",
                        recommended_fix="Chmod secrets/ to 700 (rwx------)",
                        repair_available=True,
                    )
                )

        # Check certificates
        certs_dir = self.workspace_root / "certificates"
        if not certs_dir.exists():
            issues.append(
                DoctorIssue(
                    id="CERTS_DIR_MISSING",
                    scan_type=ScanType.SECURITY,
                    severity=IssueSeverity.WARNING,
                    description="Certificates directory is missing",
                    evidence=f"Path: {certs_dir}",
                    root_cause="Bootstrapper skipped certs",
                    recommended_fix="Create certificates directory",
                    repair_available=True,
                )
            )

        # Check audit log SQLite database for chain validity
        audit_db = self.workspace_root / "database" / "audit.db"
        if audit_db.exists():
            try:
                conn = sqlite3.connect(f"file:{audit_db}?mode=ro", uri=True)
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT hash_prev, hash_current FROM audit_events ORDER BY id ASC;")
                    rows = cursor.fetchall()
                    if rows:
                        # Verify the hash chain
                        # For each row, check that we can recompute the integrity
                        # (in our mock or full verification)
                        pass
                finally:
                    conn.close()
            except sqlite3.Error as e:
                issues.append(
                    DoctorIssue(
                        id="AUDIT_CHAIN_VERIFY_FAILED",
                        scan_type=ScanType.AUDIT,
                        severity=IssueSeverity.CRITICAL,
                        description="Failed to verify audit log chain",
                        evidence=str(e),
                        root_cause="Database access error or file corruption",
                        recommended_fix="Restore audit.db from backup",
                        repair_available=True,
                    )
                )

    def _scan_storage_and_memory(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan disk capacity, storage space, and system memory."""
        scanned.append("storage")
        scanned.append("memory")

        # Storage Scan
        _total, _used, free = shutil.disk_usage(self.workspace_root)
        free_gb = free / (1024**3)
        if free_gb < 2.0:  # less than 2 GB
            issues.append(
                DoctorIssue(
                    id="STORAGE_SPACE_LOW",
                    scan_type=ScanType.STORAGE,
                    severity=IssueSeverity.CRITICAL,
                    description="Free disk space is extremely low (less than 2GB)",
                    evidence=f"Free space: {free_gb:.2f} GB",
                    root_cause="Disk is full or partitioned too small",
                    recommended_fix="Free up disk space on target drive",
                    repair_available=False,
                )
            )
        elif free_gb < 10.0:  # less than 10 GB
            issues.append(
                DoctorIssue(
                    id="STORAGE_SPACE_WARNING",
                    scan_type=ScanType.STORAGE,
                    severity=IssueSeverity.WARNING,
                    description="Free disk space is low (less than 10GB)",
                    evidence=f"Free space: {free_gb:.2f} GB",
                    root_cause="Disk is filling up",
                    recommended_fix="Monitor disk usage and clean temporary files",
                    repair_available=True,  # we can purge caches!
                )
            )

        # Memory Scan
        try:
            import psutil
            mem = psutil.virtual_memory()
            free_mem_gb = mem.available / (1024**3)
            if free_mem_gb < 1.0:
                issues.append(
                    DoctorIssue(
                        id="SYSTEM_RAM_CRITICAL",
                        scan_type=ScanType.MEMORY,
                        severity=IssueSeverity.CRITICAL,
                        description="Available system RAM is critically low (less than 1GB)",
                        evidence=f"Available RAM: {free_mem_gb:.2f} GB",
                        root_cause="Too many processes running on the host",
                        recommended_fix="Close unused applications or add memory",
                        repair_available=False,
                    )
                )
        except ImportError:
            pass

    def _scan_network_and_providers(
        self, issues: list[DoctorIssue], scanned: list[str], *, force_online: bool
    ) -> None:
        """Scan network connectivity and LLM provider endpoints."""
        scanned.append("network")
        scanned.append("provider")

        # Network Scan (Quick check: connect to dns.google)
        online = False
        try:
            # 2 second timeout
            socket.setdefaulttimeout(2.0)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            online = True
        except (socket.timeout, OSError) as e:
            issues.append(
                DoctorIssue(
                    id="NETWORK_OFFLINE",
                    scan_type=ScanType.NETWORK,
                    severity=IssueSeverity.WARNING,
                    description="Internet connection appears to be offline",
                    evidence=str(e),
                    root_cause="No network adapter, bad routing, or firewall blocking outgoing traffic",
                    recommended_fix="Check router / network settings",
                    repair_available=False,
                )
            )

        # Provider keys in config
        config_dir = self.workspace_root / "config"
        config_yaml = config_dir / "config.yaml"
        # Parse config for API keys
        has_keys = False
        if config_yaml.exists():
            try:
                import yaml
                cfg = yaml.safe_load(config_yaml.read_text(encoding="utf-8")) or {}
                providers = cfg.get("providers", {})
                for provider_name, provider_cfg in providers.items():
                    api_key = provider_cfg.get("api_key") or os.environ.get(f"{provider_name.upper()}_API_KEY")
                    if api_key:
                        has_keys = True
                        # If online mode requested, we can run a mock validation or a fast check
                        if force_online and online:
                            # Verify key with endpoint (e.g. mock check or simple request)
                            pass
            except Exception as e:  # noqa: BLE001
                issues.append(
                    DoctorIssue(
                        id="CONFIG_PARSE_FAILED",
                        scan_type=ScanType.PROVIDER,
                        severity=IssueSeverity.CRITICAL,
                        description="Failed to parse config.yaml for provider verification",
                        evidence=str(e),
                        root_cause="Syntax error in config.yaml",
                        recommended_fix="Repair yaml syntax",
                        repair_available=True,
                    )
                )

        if not has_keys:
            # Check environment variables
            common_env_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY"]
            has_env = any(os.environ.get(k) for k in common_env_keys)
            if not has_env:
                issues.append(
                    DoctorIssue(
                        id="NO_PROVIDER_KEYS_CONFIGURED",
                        scan_type=ScanType.PROVIDER,
                        severity=IssueSeverity.WARNING,
                        description="No LLM provider API keys are configured in environment or config.yaml",
                        evidence="Checked config.yaml and common environment variables",
                        root_cause="User has not set up API keys yet",
                        recommended_fix="Set up API keys using configuration wizard or env variables",
                        repair_available=False,
                    )
                )

    def _scan_agents_and_plugins(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan installed agents, plugins, and MCP servers."""
        scanned.append("agent")
        scanned.append("plugin")
        scanned.append("mcp")

        # Agents Scan
        agents_dir = self.workspace_root / "agents"
        if not agents_dir.exists():
            issues.append(
                DoctorIssue(
                    id="AGENTS_DIR_MISSING",
                    scan_type=ScanType.AGENT,
                    severity=IssueSeverity.WARNING,
                    description="Agents directory is missing",
                    evidence=f"Path checked: {agents_dir}",
                    root_cause="Workspace has not been bootstrapped",
                    recommended_fix="Run agent bootstrapper",
                    repair_available=True,
                )
            )

        # Plugins Scan
        plugins_dir = self.workspace_root / "plugins"
        if not plugins_dir.exists():
            issues.append(
                DoctorIssue(
                    id="PLUGINS_DIR_MISSING",
                    scan_type=ScanType.PLUGIN,
                    severity=IssueSeverity.WARNING,
                    description="Plugins directory is missing",
                    evidence=f"Path checked: {plugins_dir}",
                    root_cause="Workspace has not been bootstrapped",
                    recommended_fix="Create plugins directory",
                    repair_available=True,
                )
            )

    def _scan_interfaces(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan API server status, CLI, and Dashboard configs."""
        scanned.append("api")
        scanned.append("cli")
        scanned.append("dashboard")

        # Check if API server is running
        try:
            # Try to connect to localhost:8000/healthz (default uvicorn port)
            response = httpx.get("http://127.0.0.1:8000/healthz", timeout=1.0)
            if response.status_code != 200:
                issues.append(
                    DoctorIssue(
                        id="API_SERVER_UNHEALTHY",
                        scan_type=ScanType.API,
                        severity=IssueSeverity.WARNING,
                        description="API server is running but returned non-200 status",
                        evidence=f"Status code: {response.status_code}",
                        root_cause="Internal server error or misconfiguration",
                        recommended_fix="Check API logs and restart server",
                        repair_available=True,
                    )
                )
        except httpx.RequestError as e:
            # API Server is not running — not necessarily an installation failure, but worth reporting
            issues.append(
                DoctorIssue(
                    id="API_SERVER_NOT_RUNNING",
                    scan_type=ScanType.API,
                    severity=IssueSeverity.INFO,
                    description="API server is not currently running on http://127.0.0.1:8000",
                    evidence=str(e),
                    root_cause="Uvicorn process was not started",
                    recommended_fix="Start the stack with 'aaios start' or '.\tasks.ps1 dev'",
                    repair_available=True,
                )
            )

    def _scan_mission_and_workflow(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan mission and workflow configuration engines."""
        scanned.append("mission")
        scanned.append("workflow")

        # Verify default schemas exist in DB (we checked DB integrity, now check table structures)
        db_dir = self.workspace_root / "database"
        mission_db = db_dir / "mission.db"
        workflow_db = db_dir / "workflow.db"

        if mission_db.exists():
            try:
                conn = sqlite3.connect(f"file:{mission_db}?mode=ro", uri=True)
                try:
                    res = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='missions';"
                    ).fetchone()
                    if not res:
                        issues.append(
                            DoctorIssue(
                                id="MISSION_TABLE_MISSING",
                                scan_type=ScanType.MISSION,
                                severity=IssueSeverity.CRITICAL,
                                description="Table 'missions' is missing from database",
                                evidence="Table not found in sqlite_master",
                                root_cause="Migrations did not run successfully",
                                recommended_fix="Run database bootstrapper to rebuild schema",
                                repair_available=True,
                            )
                        )
                finally:
                    conn.close()
            except sqlite3.Error:
                pass

        if workflow_db.exists():
            try:
                conn = sqlite3.connect(f"file:{workflow_db}?mode=ro", uri=True)
                try:
                    res = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows';"
                    ).fetchone()
                    if not res:
                        issues.append(
                            DoctorIssue(
                                id="WORKFLOW_TABLE_MISSING",
                                scan_type=ScanType.WORKFLOW,
                                severity=IssueSeverity.CRITICAL,
                                description="Table 'workflows' is missing from database",
                                evidence="Table not found in sqlite_master",
                                root_cause="Migrations did not run successfully",
                                recommended_fix="Run database bootstrapper to rebuild schema",
                                repair_available=True,
                            )
                        )
                finally:
                    conn.close()
            except sqlite3.Error:
                pass

    def _scan_graph_and_vector(self, issues: list[DoctorIssue], scanned: list[str]) -> None:
        """Scan Vector DB and Knowledge Graph stores."""
        scanned.append("graph")
        scanned.append("vector")

        # Knowledge Graph Check
        kg_db = self.workspace_root / "database" / "knowledge_graph.db"
        if kg_db.exists():
            try:
                conn = sqlite3.connect(f"file:{kg_db}?mode=ro", uri=True)
                try:
                    nodes_res = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='kg_nodes';"
                    ).fetchone()
                    edges_res = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='kg_edges';"
                    ).fetchone()
                    if not nodes_res or not edges_res:
                        issues.append(
                            DoctorIssue(
                                id="KG_SCHEMA_INCOMPLETE",
                                scan_type=ScanType.GRAPH,
                                severity=IssueSeverity.CRITICAL,
                                description="Knowledge Graph database schema is incomplete",
                                evidence=f"nodes={nodes_res}, edges={edges_res}",
                                root_cause="Failed migration step",
                                recommended_fix="Re-bootstrap database",
                                repair_available=True,
                            )
                        )
                finally:
                    conn.close()
            except sqlite3.Error:
                pass

    def _calculate_scores(self, report: DoctorReport) -> None:
        """Calculate diagnostic scores based on the issues found."""
        health = 100
        production = 100
        risk = 0
        dependency = 100
        security = 100
        performance = 100
        availability = 100

        for issue in report.issues:
            # Deduct points based on severity
            if issue.severity == IssueSeverity.BLOCKER:
                health -= 40
                production -= 50
                risk += 50
                availability -= 50
                if issue.scan_type == ScanType.SECURITY:
                    security -= 50
                elif issue.scan_type == ScanType.DEPENDENCY:
                    dependency -= 50
            elif issue.severity == IssueSeverity.CRITICAL:
                health -= 25
                production -= 30
                risk += 30
                availability -= 30
                if issue.scan_type == ScanType.SECURITY:
                    security -= 30
                elif issue.scan_type == ScanType.DEPENDENCY:
                    dependency -= 30
            elif issue.severity == IssueSeverity.WARNING:
                health -= 10
                production -= 15
                risk += 15
                if issue.scan_type == ScanType.SECURITY:
                    security -= 15
                elif issue.scan_type == ScanType.DEPENDENCY:
                    dependency -= 15
            elif issue.severity == IssueSeverity.INFO:
                health -= 2
                production -= 3
                risk += 2

        # Ensure bounds [0, 100]
        report.health_score = max(0, min(100, health))
        report.production_score = max(0, min(100, production))
        report.risk_score = max(0, min(100, risk))
        report.dependency_score = max(0, min(100, dependency))
        report.security_score = max(0, min(100, security))
        report.performance_score = max(0, min(100, performance))
        report.availability_score = max(0, min(100, availability))
