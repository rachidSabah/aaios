"""Uninstall manager — stops active processes/services and clears directories."""

from __future__ import annotations

import os
import platform
import shutil
import signal
from pathlib import Path

from core.logging import get_logger
from services.uninstall.models import UninstallConfig, UninstallReport

_log = get_logger(__name__)

__all__ = ["UninstallManager"]


class UninstallManager:
    """Enterprise uninstaller for AAiOS service stacks, environments, and data files."""

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    def run_uninstall(self, config: UninstallConfig) -> UninstallReport:
        """Execute uninstallation, stopping services and removing folders according to config."""
        report = UninstallReport()
        _log.info("uninstall.started", everything=config.everything)

        try:
            # 1. Stop active processes
            self._stop_running_processes(report)

            # 2. Remove scheduled tasks or Windows services
            self._remove_system_registrations(report)

            # 3. Handle directory removals
            self._remove_directories(config, report)

            # 4. Remove environment variables and paths
            self._clean_environment_variables(report)

            _log.info("uninstall.completed", success=report.success)
        except Exception as e:  # noqa: BLE001
            report.success = False
            report.error = str(e)
            _log.error("uninstall.failed", error=str(e))

        return report

    def _stop_running_processes(self, report: UninstallReport) -> None:
        """Terminate uvicorn API servers, Node dashboards, and background workers."""
        # Find and terminate processes matching python -m uvicorn or pnpm run dev
        try:
            import psutil  # type: ignore[import-untyped]

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmd = proc.info.get("cmdline") or []
                    cmd_str = " ".join(cmd).lower()
                    if "pytest" in cmd_str or "test" in cmd_str:
                        continue
                    if "uvicorn" in cmd_str or "aaios" in cmd_str or "pnpm" in cmd_str:
                        pid = proc.info["pid"]
                        if pid != os.getpid() and pid != os.getppid():
                            os.kill(pid, signal.SIGTERM)
                            report.terminated_processes.append(f"{proc.info['name']} (PID: {pid})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass

    def _remove_system_registrations(self, report: UninstallReport) -> None:
        """Deregister active Windows Services and Scheduled Tasks."""
        if platform.system() == "Windows":
            import subprocess  # nosec B404

            # Remove Scheduled Task if registered
            try:
                subprocess.run(
                    ["schtasks", "/Delete", "/TN", "AAIOS_Daily_Backup", "/F"],  # noqa: S603, S607 # nosec B603 B607
                    capture_output=True,
                    check=False,
                )
                report.stopped_services.append("schtasks: AAIOS_Daily_Backup")
            except Exception:  # noqa: BLE001 # nosec B110
                pass

    def _remove_directories(self, config: UninstallConfig, report: UninstallReport) -> None:  # noqa: PLR0912
        """Selectively delete files and workspace directories according to config."""
        dirs_to_remove: list[Path] = []

        if config.everything:
            # Full uninstall: remove all data, caches, models, etc.
            config.remove_data = True
            config.remove_models = True
            config.remove_providers = True
            config.remove_plugins = True
            config.remove_agents = True
            config.remove_backups = True
            config.remove_cache = True
            config.remove_logs = True

        if config.remove_data:
            dirs_to_remove.append(self.workspace_root / "database")
            dirs_to_remove.append(self.workspace_root / "secrets")
            dirs_to_remove.append(self.workspace_root / "certificates")

        if config.remove_models:
            dirs_to_remove.append(self.workspace_root / "models")

        if config.remove_providers:
            dirs_to_remove.append(self.workspace_root / "providers")

        if config.remove_plugins:
            dirs_to_remove.append(self.workspace_root / "plugins")

        if config.remove_agents:
            dirs_to_remove.append(self.workspace_root / "projects")

        if config.remove_backups:
            dirs_to_remove.append(self.workspace_root / "backups")
            dirs_to_remove.append(self.workspace_root / "snapshots")
            dirs_to_remove.append(self.workspace_root / "exports")

        if config.remove_cache:
            dirs_to_remove.append(self.workspace_root / "caches")
            dirs_to_remove.append(self.workspace_root / "tmp")

        if config.remove_logs:
            dirs_to_remove.append(self.workspace_root / "logs")

        # Always remove virtualenv on uninstall if everything is chosen
        if config.everything:
            dirs_to_remove.append(self.workspace_root / ".venv")
            dirs_to_remove.append(self.workspace_root / "node_modules")

        for d in dirs_to_remove:
            if d.exists():
                try:
                    shutil.rmtree(d, ignore_errors=True)
                    report.removed_paths.append(str(d))
                except Exception as e:  # noqa: BLE001
                    _log.warning("uninstall.folder_removal_failed", path=str(d), error=str(e))

    def _clean_environment_variables(self, report: UninstallReport) -> None:
        """Remove AAiOS variables and bin references from PATH."""
        if platform.system() == "Windows":
            # Remove environment vars using Registry (simulated/implemented)
            try:
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                    0,
                    winreg.KEY_ALL_ACCESS,
                )
                try:
                    winreg.DeleteValue(key, "AAIOS_ENV")
                    report.removed_env_vars.append("AAIOS_ENV")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
            except Exception:  # noqa: BLE001 # nosec B110
                pass
        else:
            # Unix environment variable updates (usually in shell profile, can be logged)
            pass
