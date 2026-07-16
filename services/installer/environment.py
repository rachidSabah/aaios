"""Phase 1 — Environment Discovery.

Detects OS, hardware, network, security, and installed tools. Produces:
  - EnvironmentReport
  - CompatibilityReport
  - InstallationPlan
  - RiskReport

All detection is best-effort: failures are recorded as ``detection_errors``
rather than raising. The detector is idempotent — repeated calls produce
the same result.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, TypeVar

from core.logging import get_logger
from services.installer.models import (
    CompatibilityReport,
    EnvironmentReport,
    InstallationMode,
    InstallationPlan,
    InstallationStage,
    InstallationStep,
    PlatformSupport,
    RiskLevel,
    RiskReport,
)

_log = get_logger(__name__)

__all__ = ["EnvironmentDetector"]

T = TypeVar("T")

# Minimum requirements
MIN_PYTHON_VERSION = (3, 12)
MIN_RAM_GB = 2.0
MIN_DISK_GB = 2.0


class EnvironmentDetector:
    """Phase 1 — detect the host environment.

    Every detection method is wrapped in a try/except so a single
    failure (e.g. wmic missing) does not abort the whole report.
    """

    # Primary supported platforms
    PRIMARY_PLATFORMS: frozenset[str] = frozenset({"windows-11"})
    SECONDARY_PLATFORMS: frozenset[str] = frozenset({
        "windows-server-2022", "windows-server-2025",
        "wsl2", "ubuntu", "debian",
    })
    EXPERIMENTAL_PLATFORMS: frozenset[str] = frozenset({
        "fedora", "arch", "macos",
    })

    def __init__(self) -> None:
        self._errors: list[str] = []

    # --- public API -----------------------------------------------------

    def detect(self) -> EnvironmentReport:
        """Run all detection and return the EnvironmentReport."""
        report = EnvironmentReport()
        report.os_name = self._detect_os_name()
        report.os_version = self._detect_os_version()
        report.os_build = self._detect_os_build()
        report.platform_support = self._classify_platform(report.os_name, report.os_version)
        report.cpu_arch = self._detect_cpu_arch()
        report.cpu_count = self._detect_cpu_count()
        report.cpu_brand = self._detect_cpu_brand()
        report.ram_total_gb = self._detect_ram_total()
        report.ram_available_gb = self._detect_ram_available()
        report.gpu = self._detect_gpus()
        report.cuda_available = self._detect_cuda(report.gpu)
        report.cuda_version = self._detect_cuda_version() if report.cuda_available else ""
        report.disk_total_gb = self._detect_disk_total()
        report.disk_available_gb = self._detect_disk_available()
        report.internet_connected, report.internet_latency_ms = self._detect_internet()
        report.corporate_proxy = self._detect_proxy()
        report.firewall_detected = self._detect_firewall()
        report.is_administrator = self._detect_admin()
        report.powershell_version = self._detect_powershell()
        report.antivirus = self._detect_antivirus()
        report.windows_defender_active = self._detect_defender()
        report.python_version = self._detect_python()
        report.python_path = self._detect_python_path()
        report.node_version = self._detect_node()
        report.node_path = self._detect_node_path()
        report.git_version = self._detect_git()
        report.git_path = self._detect_git_path()
        report.docker_version = self._detect_docker()
        report.docker_path = self._detect_docker_path()
        report.wsl_available = self._detect_wsl()
        report.wsl_version = self._detect_wsl_version() if report.wsl_available else ""
        report.hyperv_available = self._detect_hyperv()
        report.is_virtual_machine = self._detect_vm()
        report.filesystem = self._detect_filesystem()
        report.locale = self._detect_locale()
        report.timezone = self._detect_timezone()
        report.path_entries = self._detect_path_entries()
        report.path_issues = self._detect_path_issues(report.path_entries)
        report.detection_errors = list(self._errors)
        _log.info(
            "installer.environment_detected",
            os=report.os_name,
            platform_support=report.platform_support,
            python=report.python_version,
        )
        return report

    def assess_compatibility(self, report: EnvironmentReport) -> CompatibilityReport:
        """Assess compatibility against minimum requirements."""
        compat = CompatibilityReport()
        compat.platform_support = report.platform_support
        # Python
        compat.python_compatible = self._python_compatible(report.python_version)
        if not compat.python_compatible:
            compat.blockers.append(
                f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required, "
                f"found {report.python_version or 'none'}"
            )
        # RAM
        compat.ram_sufficient = report.ram_total_gb >= MIN_RAM_GB
        if not compat.ram_sufficient:
            compat.blockers.append(
                f"RAM >= {MIN_RAM_GB} GB required, found {report.ram_total_gb:.1f} GB"
            )
        # Disk
        compat.disk_sufficient = report.disk_available_gb >= MIN_DISK_GB
        if not compat.disk_sufficient:
            compat.blockers.append(
                f"Disk >= {MIN_DISK_GB} GB required, found {report.disk_available_gb:.1f} GB available"
            )
        # Network
        compat.network_available = report.internet_connected
        if not compat.network_available:
            compat.warnings.append("No internet connection — offline installation only")
        # Platform
        if report.platform_support == PlatformSupport.UNSUPPORTED.value:
            compat.blockers.append(
                f"Unsupported platform: {report.os_name} {report.os_version}"
            )
        elif report.platform_support == PlatformSupport.EXPERIMENTAL.value:
            compat.warnings.append(
                f"Experimental platform: {report.os_name} {report.os_version}"
            )
        # Administrator
        if not report.is_administrator:
            compat.warnings.append(
                "Not running as administrator — some operations may fail"
            )
        # Recommendations
        if not report.git_version:
            compat.recommendations.append("Install Git for version control")
        if not report.node_version:
            compat.recommendations.append("Install Node.js 20+ for the dashboard")
        if not report.docker_version:
            compat.recommendations.append("Install Docker for containerized deployments")
        compat.compatible = not compat.blockers
        return compat

    def build_plan(
        self,
        report: EnvironmentReport,
        compat: CompatibilityReport,
        mode: InstallationMode | str,
        workspace_root: str = "",
    ) -> InstallationPlan:
        """Build an installation plan from the environment + compatibility."""
        m = InstallationMode(mode) if isinstance(mode, str) else mode
        plan = InstallationPlan(
            mode=m.value,
            workspace_root=workspace_root or self._default_workspace_root(m),
            profile=self._default_profile(m),
            requires_admin=not report.is_administrator,
        )
        # Always start with environment discovery
        plan.steps.append(InstallationStep(
            stage=InstallationStage.ENVIRONMENT_DISCOVERY.value,
            name="Environment Discovery",
            description="Detect OS, hardware, network, and installed tools.",
            estimated_seconds=2.0,
            can_skip=False,
        ))
        # Dependency discovery
        plan.steps.append(InstallationStep(
            stage=InstallationStage.DEPENDENCY_DISCOVERY.value,
            name="Dependency Discovery",
            description="Check required and optional dependencies.",
            estimated_seconds=10.0,
            dependencies=[plan.steps[-1].step_id],
            can_skip=False,
        ))
        # Workspace bootstrap
        plan.steps.append(InstallationStep(
            stage=InstallationStage.WORKSPACE_BOOTSTRAP.value,
            name="Workspace Bootstrap",
            description=f"Create workspace at {plan.workspace_root}",
            estimated_seconds=5.0,
            dependencies=[plan.steps[-1].step_id],
            can_skip=False,
        ))
        # Database bootstrap
        plan.steps.append(InstallationStep(
            stage=InstallationStage.DATABASE_BOOTSTRAP.value,
            name="Database Bootstrap",
            description="Initialize SQLite, Qdrant, and memory stores.",
            estimated_seconds=15.0,
            dependencies=[plan.steps[-1].step_id],
            can_skip=(m in (InstallationMode.VALIDATE, InstallationMode.MINIMAL)),
        ))
        # Configuration
        plan.steps.append(InstallationStep(
            stage=InstallationStage.CONFIGURATION.value,
            name="Configuration Wizard",
            description=f"Apply {plan.profile} profile.",
            estimated_seconds=5.0,
            dependencies=[plan.steps[-1].step_id],
            can_skip=False,
        ))
        # Provider configuration
        if m not in (InstallationMode.MINIMAL, InstallationMode.VALIDATE):
            plan.steps.append(InstallationStep(
                stage=InstallationStage.PROVIDER_CONFIGURATION.value,
                name="Provider Configuration",
                description="Discover and validate LLM providers.",
                estimated_seconds=20.0,
                dependencies=[plan.steps[-1].step_id],
                can_skip=True,
            ))
        # Agent bootstrap
        if m not in (InstallationMode.MINIMAL, InstallationMode.VALIDATE):
            plan.steps.append(InstallationStep(
                stage=InstallationStage.AGENT_BOOTSTRAP.value,
                name="Agent Bootstrap",
                description="Discover and register supported agents.",
                estimated_seconds=10.0,
                dependencies=[plan.steps[-1].step_id],
                can_skip=True,
            ))
        # Validation
        plan.steps.append(InstallationStep(
            stage=InstallationStage.VALIDATION.value,
            name="Validation",
            description="Verify the installation.",
            estimated_seconds=5.0,
            dependencies=[plan.steps[-1].step_id],
            can_skip=False,
        ))
        plan.total_estimated_seconds = sum(s.estimated_seconds for s in plan.steps)
        return plan

    def assess_risks(
        self,
        report: EnvironmentReport,
        compat: CompatibilityReport,
    ) -> RiskReport:
        """Assess installation risks."""
        risks: list[dict[str, Any]] = []
        mitigations: list[str] = []
        if not compat.compatible:
            risks.append({
                "category": "compatibility",
                "level": RiskLevel.CRITICAL.value,
                "description": "Compatibility blockers detected",
                "blockers": compat.blockers,
            })
            mitigations.append("Resolve compatibility blockers before retrying.")
        if not report.internet_connected:
            risks.append({
                "category": "network",
                "level": RiskLevel.HIGH.value,
                "description": "No internet connection",
            })
            mitigations.append("Use --offline mode or connect to the internet.")
        if not report.is_administrator:
            risks.append({
                "category": "privileges",
                "level": RiskLevel.MEDIUM.value,
                "description": "Not running as administrator",
            })
            mitigations.append("Re-run as administrator for full installation.")
        if report.disk_available_gb < MIN_DISK_GB * 2:
            risks.append({
                "category": "disk",
                "level": RiskLevel.MEDIUM.value,
                "description": "Low disk space",
            })
            mitigations.append("Free up at least 10 GB of disk space.")
        if report.platform_support == PlatformSupport.EXPERIMENTAL.value:
            risks.append({
                "category": "platform",
                "level": RiskLevel.MEDIUM.value,
                "description": "Experimental platform",
            })
            mitigations.append("Test thoroughly before production use.")
        if report.firewall_detected:
            risks.append({
                "category": "firewall",
                "level": RiskLevel.LOW.value,
                "description": "Firewall detected — may block downloads",
            })
            mitigations.append("Whitelist aaios and python in the firewall.")
        # Overall risk
        if any(r["level"] == RiskLevel.CRITICAL.value for r in risks):
            overall = RiskLevel.CRITICAL.value
        elif any(r["level"] == RiskLevel.HIGH.value for r in risks):
            overall = RiskLevel.HIGH.value
        elif any(r["level"] == RiskLevel.MEDIUM.value for r in risks):
            overall = RiskLevel.MEDIUM.value
        elif any(r["level"] == RiskLevel.LOW.value for r in risks):
            overall = RiskLevel.LOW.value
        else:
            overall = RiskLevel.INFO.value
        return RiskReport(overall_risk=overall, risks=risks, mitigations=mitigations)

    # --- detection helpers ---------------------------------------------

    def _safe(self, fn: Any, *args: Any, default: T) -> T:
        try:
            result = fn(*args)
            return result  # type: ignore[no-any-return]
        except Exception as e:  # noqa: BLE001
            self._errors.append(f"{getattr(fn, '__name__', 'detect')}: {e}")
            return default

    def _detect_os_name(self) -> str:
        return self._safe(lambda: platform.system().lower(), default="unknown")

    def _detect_os_version(self) -> str:
        return self._safe(lambda: platform.version(), default="")

    def _detect_os_build(self) -> str:
        return self._safe(lambda: platform.win32_ver()[2] if hasattr(platform, "win32_ver") else "", default="")

    def _classify_platform(self, name: str, version: str) -> str:
        n = name.lower()
        v = version.lower()
        if n == "windows":
            if "10.0.22" in v and "10.0.22000" in v:
                return PlatformSupport.PRIMARY.value
            if "10.0.22" in v:  # 22621+ = Win 11
                return PlatformSupport.PRIMARY.value
            if "server" in v:
                return PlatformSupport.SECONDARY.value
            return PlatformSupport.SECONDARY.value
        if n == "linux":
            if "microsoft" in v or "wsl" in v:
                return PlatformSupport.SECONDARY.value
            try:
                import distro
                d = distro.id()
                if d in ("ubuntu", "debian"):
                    return PlatformSupport.SECONDARY.value
                if d in ("fedora", "arch"):
                    return PlatformSupport.EXPERIMENTAL.value
            except ImportError:
                pass
            return PlatformSupport.SECONDARY.value
        if n == "darwin":
            return PlatformSupport.EXPERIMENTAL.value
        return PlatformSupport.UNSUPPORTED.value

    def _detect_cpu_arch(self) -> str:
        return self._safe(lambda: platform.machine(), default="unknown")

    def _detect_cpu_count(self) -> int:
        return self._safe(lambda: os.cpu_count() or 0, default=0)

    def _detect_cpu_brand(self) -> str:
        return self._safe(lambda: platform.processor(), default="unknown")

    def _detect_ram_total(self) -> float:
        return self._safe(self._ram_total, default=0.0)

    def _detect_ram_available(self) -> float:
        return self._safe(self._ram_available, default=0.0)

    def _ram_total(self) -> float:
        try:
            import psutil
            return float(psutil.virtual_memory().total / (1024 ** 3))
        except ImportError:
            return 0.0

    def _ram_available(self) -> float:
        try:
            import psutil
            return float(psutil.virtual_memory().available / (1024 ** 3))
        except ImportError:
            return 0.0

    def _detect_gpus(self) -> list[str]:
        gpus: list[str] = []
        # Try nvidia-smi
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi:
            try:
                result = subprocess.run(
                    [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5, check=False,
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if line.strip():
                            gpus.append(line.strip())
            except (subprocess.SubprocessError, OSError):
                pass
        return gpus

    def _detect_cuda(self, gpus: list[str]) -> bool:
        if not gpus:
            return False
        nvidia_smi = shutil.which("nvidia-smi")
        return bool(nvidia_smi)

    def _detect_cuda_version(self) -> str:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return ""
        try:
            result = subprocess.run(
                [nvidia_smi, "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()[0]
        except (subprocess.SubprocessError, OSError):
            pass
        return ""

    def _detect_disk_total(self) -> float:
        return self._safe(self._disk_total, default=0.0)

    def _detect_disk_available(self) -> float:
        return self._safe(self._disk_available, default=0.0)

    def _disk_total(self) -> float:
        try:
            import psutil
            return float(psutil.disk_usage("/").total / (1024 ** 3))
        except ImportError:
            return 0.0

    def _disk_available(self) -> float:
        try:
            import psutil
            return float(psutil.disk_usage("/").free / (1024 ** 3))
        except ImportError:
            return 0.0

    def _detect_internet(self) -> tuple[bool, float]:
        try:
            start = time.monotonic()
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            latency = (time.monotonic() - start) * 1000
            return True, round(latency, 2)
        except OSError:
            return False, 0.0

    def _detect_proxy(self) -> str:
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            val = os.environ.get(var)
            if val:
                return val
        return ""

    def _detect_firewall(self) -> bool:
        if platform.system().lower() == "windows":
            try:
                result = subprocess.run(
                    ["netsh", "advfirewall", "show", "allprofiles", "state"],
                    capture_output=True, text=True, timeout=5, check=False,
                )
                return "ON" in result.stdout
            except (subprocess.SubprocessError, OSError):
                return False
        # Linux: assume ufw or firewalld presence means a firewall
        return bool(shutil.which("ufw") or shutil.which("firewall-cmd"))

    def _detect_admin(self) -> bool:
        if platform.system().lower() == "windows":
            try:
                import ctypes
                return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                return False
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False

    def _detect_powershell(self) -> str:
        if platform.system().lower() != "windows":
            return ""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass
        return ""

    def _detect_antivirus(self) -> list[str]:
        avs: list[str] = []
        if platform.system().lower() == "windows":
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-CimInstance -Namespace 'root/SecurityCenter2' -ClassName AntivirusProduct | "
                     "Select-Object -ExpandProperty displayName"],
                    capture_output=True, text=True, timeout=5, check=False,
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if line.strip():
                            avs.append(line.strip())
            except (subprocess.SubprocessError, OSError):
                pass
        return avs

    def _detect_defender(self) -> bool:
        if platform.system().lower() != "windows":
            return False
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-MpComputerStatus).RealTimeProtectionEnabled"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            return "True" in result.stdout
        except (subprocess.SubprocessError, OSError):
            return False

    def _detect_python(self) -> str:
        return platform.python_version()

    def _detect_python_path(self) -> str:
        return sys.executable

    def _detect_node(self) -> str:
        return self._tool_version("node")

    def _detect_node_path(self) -> str:
        return shutil.which("node") or ""

    def _detect_git(self) -> str:
        return self._tool_version("git")

    def _detect_git_path(self) -> str:
        return shutil.which("git") or ""

    def _detect_docker(self) -> str:
        return self._tool_version("docker")

    def _detect_docker_path(self) -> str:
        return shutil.which("docker") or ""

    def _detect_wsl(self) -> bool:
        if platform.system().lower() == "windows":
            return bool(shutil.which("wsl"))
        # If we're on Linux, check for WSL markers
        try:
            with open("/proc/version") as f:
                content = f.read()
            return "microsoft" in content.lower() or "wsl" in content.lower()
        except OSError:
            return False

    def _detect_wsl_version(self) -> str:
        if platform.system().lower() == "windows":
            return self._tool_version("wsl") or ""
        return ""

    def _detect_hyperv(self) -> bool:
        if platform.system().lower() != "windows":
            return False
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V).State"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            return "Enabled" in result.stdout
        except (subprocess.SubprocessError, OSError):
            return False

    def _detect_vm(self) -> bool:
        manufacturer = self._safe(
            lambda: platform.system().lower(), default=""
        )
        # Heuristic: check for VM-specific markers
        if manufacturer == "linux":
            try:
                result = subprocess.run(
                    ["systemd-detect-virt"],
                    capture_output=True, text=True, timeout=3, check=False,
                )
                if result.returncode == 0 and result.stdout.strip().lower() != "none":
                    return True
            except (subprocess.SubprocessError, OSError):
                pass
        return False

    def _detect_filesystem(self) -> str:
        return self._safe(lambda: os.statvfs("/").f_fsid.__class__.__name__ if hasattr(os, "statvfs") else "unknown", default="unknown")

    def _detect_locale(self) -> str:
        return os.environ.get("LANG", os.environ.get("LC_ALL", ""))

    def _detect_timezone(self) -> str:
        return time.tzname[0] if time.tzname else ""

    def _detect_path_entries(self) -> list[str]:
        return os.environ.get("PATH", "").split(os.pathsep)

    def _detect_path_issues(self, entries: list[str]) -> list[str]:
        issues: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            if not entry:
                continue
            if entry in seen:
                issues.append(f"Duplicate PATH entry: {entry}")
            seen.add(entry)
            if not Path(entry).exists():
                issues.append(f"PATH entry does not exist: {entry}")
        return issues

    def _tool_version(self, tool: str) -> str:
        path = shutil.which(tool)
        if not path:
            return ""
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode == 0:
                # Take the first non-empty line
                for line in result.stdout.splitlines():
                    if line.strip():
                        return str(line.strip()[:100])
            return ""
        except (subprocess.SubprocessError, OSError):
            return ""

    def _python_compatible(self, version_str: str) -> bool:
        if not version_str:
            return False
        try:
            parts = version_str.split(".")
            major, minor = int(parts[0]), int(parts[1])
            return (major, minor) >= MIN_PYTHON_VERSION
        except (ValueError, IndexError):
            return False

    def _default_workspace_root(self, mode: InstallationMode) -> str:
        if mode == InstallationMode.PORTABLE:
            return str(Path.cwd() / "aaios-portable")
        if platform.system().lower() == "windows":
            return str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AAiOS")
        return str(Path.home() / ".aaios")

    def _default_profile(self, mode: InstallationMode) -> str:
        if mode in (InstallationMode.DEVELOPER, InstallationMode.INTERACTIVE):
            return "development"
        if mode in (InstallationMode.ENTERPRISE,):
            return "enterprise"
        if mode in (InstallationMode.MINIMAL, InstallationMode.PORTABLE):
            return "minimal"
        return "production"
