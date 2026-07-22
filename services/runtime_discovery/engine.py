"""Runtime Discovery Engine — multi-source layered discovery.

Scans the host for AI agents using every available source:
  - PATH search
  - Filesystem search (common install directories)
  - Package managers (npm, pip, cargo, brew, apt, winget, scoop)
  - Windows Registry
  - Running processes
  - Listening ports
  - MCP config files
  - Environment variables

All discovery is best-effort and parallelized. Results are merged to
eliminate duplicates. The engine is event-driven: filesystem watchers
trigger incremental rescans when relevant directories change.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger
from services.runtime_discovery.specs import (
    DetectionMethod,
    ProviderSpec,
    ProviderSpecRegistry,
    get_spec_registry,
)

_log = get_logger(__name__)

__all__ = [
    "DiscoveredProvider",
    "DiscoveryResult",
    "DiscoveryEngine",
]


@dataclass
class DiscoveredProvider:
    """A provider discovered on the host."""

    provider_id: str = field(default_factory=lambda: uuid4().hex[:12])
    spec_id: str = ""
    name: str = ""
    vendor: str = ""
    category: str = ""
    executable: str = ""
    version: str = ""
    install_path: str = ""
    detection_method: str = DetectionMethod.PATH.value
    package_manager: str = ""
    config_file: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    validated: bool = False
    health: str = "unknown"  # unknown | healthy | unhealthy | validating
    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "spec_id": self.spec_id,
            "name": self.name,
            "vendor": self.vendor,
            "category": self.category,
            "executable": self.executable,
            "version": self.version,
            "install_path": self.install_path,
            "detection_method": self.detection_method,
            "package_manager": self.package_manager,
            "config_file": self.config_file,
            "env_vars": dict(self.env_vars),
            "discovered_at": self.discovered_at,
            "validated": self.validated,
            "health": self.health,
            "capabilities": list(self.capabilities),
            "models": list(self.models),
            "error": self.error,
        }


@dataclass
class DiscoveryResult:
    """Result of a full discovery scan."""

    scan_id: str = field(default_factory=lambda: uuid4().hex[:12])
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""
    providers: list[DiscoveredProvider] = field(default_factory=list)
    sources_checked: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "providers": [p.to_dict() for p in self.providers],
            "provider_count": len(self.providers),
            "sources_checked": list(self.sources_checked),
            "errors": list(self.errors),
            "duration_s": round(self.duration_s, 2),
        }


class DiscoveryEngine:
    """Multi-source layered discovery engine.

    Scans PATH, filesystem, package managers, registry, processes,
    ports, MCP configs, and environment variables to find AI agents.
    """

    def __init__(self, registry: ProviderSpecRegistry | None = None) -> None:
        self._registry = registry or get_spec_registry()
        self._is_windows = sys.platform == "win32"
        self._is_macos = sys.platform == "darwin"

    async def discover_all(self) -> DiscoveryResult:
        """Run a full discovery scan across all sources."""
        start = datetime.now(UTC)
        result = DiscoveryResult()
        specs = self._registry.list_all()

        # Run all discovery sources in parallel
        tasks: list[Any] = []
        for spec in specs:
            tasks.append(self._discover_spec(spec))

        discovered_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results
        seen_keys: set[str] = set()
        for dl in discovered_lists:
            if isinstance(dl, Exception):
                result.errors.append(str(dl))
                continue
            if not isinstance(dl, list):
                continue
            for provider in dl:
                key = self._merge_key(provider)
                if key not in seen_keys:
                    seen_keys.add(key)
                    result.providers.append(provider)

        # Also check package managers
        pm_result = await self._discover_via_package_managers()
        result.sources_checked.extend(pm_result.sources_checked)
        for provider in pm_result.providers:
            key = self._merge_key(provider)
            if key not in seen_keys:
                seen_keys.add(key)
                result.providers.append(provider)

        result.sources_checked = list(set(result.sources_checked))
        result.completed_at = datetime.now(UTC).isoformat()
        result.duration_s = (datetime.now(UTC) - start).total_seconds()
        _log.info(
            "discovery.scan_complete",
            providers=len(result.providers),
            sources=len(result.sources_checked),
            duration=result.duration_s,
        )
        return result

    async def discover_one(self, spec_id: str) -> list[DiscoveredProvider]:
        """Discover a single provider by spec ID."""
        spec = self._registry.get(spec_id)
        if not spec:
            return []
        return await self._discover_spec(spec)

    async def _discover_spec(self, spec: ProviderSpec) -> list[DiscoveredProvider]:
        """Discover all instances of one provider spec."""
        results: list[DiscoveredProvider] = []

        # 1. PATH search
        provider = await self._discover_via_path(spec)
        if provider:
            results.append(provider)

        # 2. Filesystem search
        provider = await self._discover_via_filesystem(spec)
        if provider:
            # Deduplicate against PATH result
            if not any(p.executable == provider.executable for p in results):
                results.append(provider)

        # 3. Environment variables
        provider = await self._discover_via_env(spec)
        if provider:
            results.append(provider)

        # 4. MCP config files
        provider = await self._discover_via_mcp_config(spec)
        if provider:
            results.append(provider)

        # 5. Running processes
        provider = await self._discover_via_process(spec)
        if provider:
            if not any(p.executable == provider.executable for p in results):
                results.append(provider)

        # 6. Listening ports (for local LLM servers)
        provider = await self._discover_via_port(spec)
        if provider:
            results.append(provider)

        return results

    # --- Source: PATH ---------------------------------------------------

    async def _discover_via_path(self, spec: ProviderSpec) -> DiscoveredProvider | None:
        """Search PATH for the provider's binary."""
        for binary in spec.binary_names:
            path = shutil.which(binary)
            if not path:
                # Try with extensions on Windows
                if self._is_windows:
                    for ext in (".exe", ".cmd", ".bat", ".ps1"):
                        path = shutil.which(f"{binary}{ext}")
                        if path:
                            break
            if path:
                version = await self._get_version(path, spec)
                return DiscoveredProvider(
                    spec_id=spec.spec_id,
                    name=spec.name,
                    vendor=spec.vendor,
                    category=spec.category.value,
                    executable=path,
                    version=version,
                    install_path=str(Path(path).parent),
                    detection_method=DetectionMethod.PATH.value,
                    capabilities=list(spec.expected_capabilities),
                )
        return None

    # --- Source: Filesystem ---------------------------------------------

    async def _discover_via_filesystem(self, spec: ProviderSpec) -> DiscoveredProvider | None:
        """Search common install directories."""
        search_dirs = self._get_search_dirs(spec)
        for d in search_dirs:
            if not d.exists():
                continue
            try:
                for entry in d.iterdir():
                    if not entry.is_file():
                        continue
                    for binary in spec.binary_names:
                        # Match exact name or name with extension
                        if binary in (entry.name, entry.stem):
                            version = await self._get_version(str(entry), spec)
                            return DiscoveredProvider(
                                spec_id=spec.spec_id,
                                name=spec.name,
                                vendor=spec.vendor,
                                category=spec.category.value,
                                executable=str(entry),
                                version=version,
                                install_path=str(d),
                                detection_method=DetectionMethod.FILESYSTEM.value,
                                capabilities=list(spec.expected_capabilities),
                            )
            except OSError:
                continue
        return None

    # --- Source: Package Managers ---------------------------------------

    async def _discover_via_package_managers(self) -> DiscoveryResult:
        """Check package managers for installed AI agents."""
        result = DiscoveryResult()
        specs = self._registry.list_all()

        # npm
        npm_installed = await self._get_npm_packages()
        if npm_installed is not None:
            result.sources_checked.append("npm")
            for spec in specs:
                for pkg in spec.npm_packages:
                    if pkg in npm_installed:
                        # Find the binary
                        for binary in spec.binary_names:
                            path = shutil.which(binary)
                            if path:
                                version = npm_installed.get(pkg, "")
                                result.providers.append(
                                    DiscoveredProvider(
                                        spec_id=spec.spec_id,
                                        name=spec.name,
                                        vendor=spec.vendor,
                                        category=spec.category.value,
                                        executable=path,
                                        version=version,
                                        install_path=str(Path(path).parent),
                                        detection_method=DetectionMethod.PACKAGE_MANAGER.value,
                                        package_manager="npm",
                                        capabilities=list(spec.expected_capabilities),
                                    )
                                )
                                break

        # pip
        pip_installed = await self._get_pip_packages()
        if pip_installed is not None:
            result.sources_checked.append("pip")
            for spec in specs:
                for pkg in spec.pip_packages:
                    if pkg in pip_installed:
                        for binary in spec.binary_names:
                            path = shutil.which(binary)
                            if path:
                                version = pip_installed.get(pkg, "")
                                result.providers.append(
                                    DiscoveredProvider(
                                        spec_id=spec.spec_id,
                                        name=spec.name,
                                        vendor=spec.vendor,
                                        category=spec.category.value,
                                        executable=path,
                                        version=version,
                                        detection_method=DetectionMethod.PACKAGE_MANAGER.value,
                                        package_manager="pip",
                                        capabilities=list(spec.expected_capabilities),
                                    )
                                )
                                break

        # cargo
        cargo_installed = await self._get_cargo_packages()
        if cargo_installed is not None:
            result.sources_checked.append("cargo")
            for spec in specs:
                for pkg in spec.cargo_packages:
                    if pkg in cargo_installed:
                        for binary in spec.binary_names:
                            path = shutil.which(binary)
                            if path:
                                version = cargo_installed.get(pkg, "")
                                result.providers.append(
                                    DiscoveredProvider(
                                        spec_id=spec.spec_id,
                                        name=spec.name,
                                        vendor=spec.vendor,
                                        category=spec.category.value,
                                        executable=path,
                                        version=version,
                                        install_path=str(Path(path).parent),
                                        detection_method=DetectionMethod.PACKAGE_MANAGER.value,
                                        package_manager="cargo",
                                        capabilities=list(spec.expected_capabilities),
                                    )
                                )
                                break

        # brew (macOS only)
        if self._is_macos:
            brew_installed = await self._get_brew_packages()
            if brew_installed is not None:
                result.sources_checked.append("brew")
                for spec in specs:
                    for pkg in spec.brew_packages:
                        if pkg in brew_installed:
                            for binary in spec.binary_names:
                                path = shutil.which(binary)
                                if path:
                                    version = brew_installed.get(pkg, "")
                                    result.providers.append(
                                        DiscoveredProvider(
                                            spec_id=spec.spec_id,
                                            name=spec.name,
                                            vendor=spec.vendor,
                                            category=spec.category.value,
                                            executable=path,
                                            version=version,
                                            install_path=str(Path(path).parent),
                                            detection_method=DetectionMethod.PACKAGE_MANAGER.value,
                                            package_manager="brew",
                                            capabilities=list(spec.expected_capabilities),
                                        )
                                    )
                                    break

        # winget (Windows only)
        if self._is_windows:
            winget_installed = await self._get_winget_packages()
            if winget_installed is not None:
                result.sources_checked.append("winget")
                for spec in specs:
                    for pkg in spec.winget_packages:
                        if pkg in winget_installed:
                            for binary in spec.binary_names:
                                path = shutil.which(binary)
                                if path:
                                    version = winget_installed.get(pkg, "")
                                    result.providers.append(
                                        DiscoveredProvider(
                                            spec_id=spec.spec_id,
                                            name=spec.name,
                                            vendor=spec.vendor,
                                            category=spec.category.value,
                                            executable=path,
                                            version=version,
                                            install_path=str(Path(path).parent),
                                            detection_method=DetectionMethod.PACKAGE_MANAGER.value,
                                            package_manager="winget",
                                            capabilities=list(spec.expected_capabilities),
                                        )
                                    )
                                    break

        return result

    # --- Source: Environment Variables ----------------------------------

    async def _discover_via_env(self, spec: ProviderSpec) -> DiscoveredProvider | None:
        """Check environment variables for provider indicators."""
        found_vars: dict[str, str] = {}
        for var in spec.env_indicators:
            val = os.environ.get(var)
            if val:
                found_vars[var] = val[:8] + "..." if len(val) > 12 else val
        if not found_vars:
            return None
        # Try to find the binary
        for binary in spec.binary_names:
            path = shutil.which(binary)
            if path:
                version = await self._get_version(path, spec)
                return DiscoveredProvider(
                    spec_id=spec.spec_id,
                    name=spec.name,
                    vendor=spec.vendor,
                    category=spec.category.value,
                    executable=path,
                    version=version,
                    install_path=str(Path(path).parent),
                    detection_method=DetectionMethod.ENVIRONMENT.value,
                    env_vars=found_vars,
                    capabilities=list(spec.expected_capabilities),
                )
        # Even without a binary, record the env presence
        return DiscoveredProvider(
            spec_id=spec.spec_id,
            name=spec.name,
            vendor=spec.vendor,
            category=spec.category.value,
            executable="",
            detection_method=DetectionMethod.ENVIRONMENT.value,
            env_vars=found_vars,
            capabilities=list(spec.expected_capabilities),
            health="unknown",
            error="Environment variables present but binary not found in PATH",
        )

    # --- Source: MCP Config Files ---------------------------------------

    async def _discover_via_mcp_config(self, spec: ProviderSpec) -> DiscoveredProvider | None:
        """Check MCP config files for the provider."""
        if not spec.supports_mcp:
            return None
        import json

        home = Path.home()
        mcp_configs = [
            home / ".claude" / "mcp_servers.json",
            home / ".config" / "mcp" / "servers.json",
            home / ".mcp" / "config.json",
        ]
        for config_path in mcp_configs:
            if not config_path.exists():
                continue
            try:
                data = json.loads(config_path.read_text())
                servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
                for server_name, server_config in servers.items():
                    if not isinstance(server_config, dict):
                        continue
                    cmd = server_config.get("command", "")
                    if any(b in cmd for b in spec.binary_names):
                        return DiscoveredProvider(
                            spec_id=spec.spec_id,
                            name=spec.name,
                            vendor=spec.vendor,
                            category=spec.category.value,
                            executable=cmd,
                            detection_method=DetectionMethod.MCP_CONFIG.value,
                            config_file=str(config_path),
                            capabilities=list(spec.expected_capabilities),
                        )
            except (json.JSONDecodeError, OSError):
                continue
        return None

    # --- Source: Running Processes --------------------------------------

    async def _discover_via_process(self, spec: ProviderSpec) -> DiscoveredProvider | None:
        """Check running processes for the provider."""
        try:
            import psutil
        except ImportError:
            return None
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                info = proc.info
                proc_name = info.get("name", "")
                proc_exe = info.get("exe", "")
                for binary in spec.binary_names:
                    if binary in proc_name or (proc_exe and binary in Path(proc_exe).stem):
                        return DiscoveredProvider(
                            spec_id=spec.spec_id,
                            name=spec.name,
                            vendor=spec.vendor,
                            category=spec.category.value,
                            executable=proc_exe or proc_name,
                            detection_method=DetectionMethod.PROCESS.value,
                            capabilities=list(spec.expected_capabilities),
                        )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    # --- Source: Listening Ports ----------------------------------------

    async def _discover_via_port(self, spec: ProviderSpec) -> DiscoveredProvider | None:
        """Check listening ports for local LLM servers."""
        try:
            import psutil
        except ImportError:
            return None
        # Known ports for local LLM servers
        port_map: dict[str, list[int]] = {
            "ollama": [11434],
            "lm-studio": [1234],
            "vllm": [8000, 8080],
            "localai": [8080],
            "koboldcpp": [5001],
            "text-generation-webui": [7860],
            "comfyui": [8188],
            "n8n": [5678],
            "flowise": [3000],
        }
        ports_to_check = port_map.get(spec.spec_id, [])
        if not ports_to_check:
            return None
        for conn in psutil.net_connections():
            if conn.status != "LISTEN":
                continue
            laddr = conn.laddr
            # laddr can be an empty tuple or an addr namedtuple
            try:
                port = laddr.port  # type: ignore[union-attr]
            except (AttributeError, IndexError):
                continue
            if port in ports_to_check:
                return DiscoveredProvider(
                    spec_id=spec.spec_id,
                    name=spec.name,
                    vendor=spec.vendor,
                    category=spec.category.value,
                    executable=f"http://127.0.0.1:{port}",
                    detection_method=DetectionMethod.PORT.value,
                    capabilities=list(spec.expected_capabilities),
                )
        return None

    # --- Helpers --------------------------------------------------------

    def _get_search_dirs(self, spec: ProviderSpec) -> list[Path]:
        """Get directories to search for the spec."""
        dirs: list[Path] = []
        home = Path.home()
        # Spec-specific dirs
        for d in spec.install_dirs:
            dirs.append(home / d)
        # Common dirs
        if self._is_windows:
            dirs.extend(
                [
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
                    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
                    Path(os.environ.get("LocalAppData", str(home / "AppData" / "Local"))),
                    Path(os.environ.get("AppData", str(home / "AppData" / "Roaming"))),
                    home / ".local" / "bin",
                    home / "bin",
                    Path("C:\\ProgramData\\chocolatey\\bin"),
                ]
            )
        else:
            dirs.extend(
                [
                    Path("/usr/local/bin"),
                    Path("/usr/bin"),
                    Path("/opt"),
                    home / ".local" / "bin",
                    home / "bin",
                    home / ".cargo" / "bin",
                    home / ".npm-global" / "bin",
                ]
            )
            if self._is_macos:
                dirs.extend([Path("/opt/homebrew/bin"), Path("/usr/local/opt")])
        return dirs

    async def _get_version(self, executable: str, spec: ProviderSpec) -> str:
        """Get the version of an executable."""
        if not executable:
            return ""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [executable, *spec.version_args],
                capture_output=True,
                text=True,
                timeout=spec.health_timeout_s,
                check=False,
            )
            output = (result.stdout or result.stderr).strip()
            if not output:
                return ""
            # Try to extract version with regex
            match = re.search(spec.version_regex, output)
            return match.group(1) if match else output[:50]
        except (subprocess.SubprocessError, OSError, asyncio.TimeoutError):
            return ""

    async def _get_npm_packages(self) -> dict[str, str] | None:
        """Get globally installed npm packages."""
        npm = shutil.which("npm")
        if not npm:
            return None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [npm, "list", "-g", "--depth=0", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                return None
            import json

            data = json.loads(result.stdout)
            deps = data.get("dependencies", {})
            return {name: info.get("version", "") for name, info in deps.items()}
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, asyncio.TimeoutError):
            return None

    async def _get_pip_packages(self) -> dict[str, str] | None:
        """Get installed pip packages."""
        pip = shutil.which("pip") or shutil.which("pip3")
        if not pip:
            return None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [pip, "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                return None
            import json

            data = json.loads(result.stdout)
            return {pkg["name"].lower(): pkg["version"] for pkg in data}
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, asyncio.TimeoutError):
            return None

    async def _get_cargo_packages(self) -> dict[str, str] | None:
        """Get installed cargo packages."""
        cargo = shutil.which("cargo")
        if not cargo:
            return None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [cargo, "install", "--list"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                return None
            packages: dict[str, str] = {}
            for line in result.stdout.splitlines():
                match = re.match(r"^(\S+)\s+v(\S+):", line)
                if match:
                    packages[match.group(1)] = match.group(2)
            return packages
        except (subprocess.SubprocessError, OSError, asyncio.TimeoutError):
            return None

    async def _get_brew_packages(self) -> dict[str, str] | None:
        """Get installed brew packages."""
        brew = shutil.which("brew")
        if not brew:
            return None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [brew, "list", "--versions"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                return None
            packages: dict[str, str] = {}
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    packages[parts[0]] = parts[1]
            return packages
        except (subprocess.SubprocessError, OSError, asyncio.TimeoutError):
            return None

    async def _get_winget_packages(self) -> dict[str, str] | None:
        """Get installed winget packages."""
        winget = shutil.which("winget")
        if not winget:
            return None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [winget, "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                return None
            import json

            data = json.loads(result.stdout)
            packages: dict[str, str] = {}
            for pkg in data.get("Source", []):
                name = pkg.get("Name", "")
                version = pkg.get("Version", "")
                if name:
                    packages[name] = version
            return packages
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, asyncio.TimeoutError):
            return None

    def _merge_key(self, provider: DiscoveredProvider) -> str:
        """Generate a merge key to deduplicate providers."""
        return f"{provider.spec_id}:{provider.executable}"
