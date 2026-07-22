"""Phase 2 — Dependency Discovery.

Discovers, verifies, and (optionally) installs required and optional
dependencies. Each dependency is classified as:

  - required: must be present for AAiOS to function
  - recommended: should be present for full functionality
  - optional: provides additional features when available

The checker is best-effort: missing optional dependencies are skipped
with a clear status, never aborting the installation.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

from core.logging import get_logger
from services.installer.models import DependencyCheck, DependencyStatus

_log = get_logger(__name__)

__all__ = ["DependencyRegistry", "DependencyChecker"]


@dataclass
class DependencySpec:
    """Specification of a single dependency."""

    name: str
    category: str  # required | recommended | optional
    tool: str = ""  # CLI tool name (for shutil.which)
    version_args: tuple[str, ...] = ("--version",)
    min_version: str = ""
    install_hint: str = ""
    can_install: bool = True
    can_skip: bool = True
    install_method: str = ""  # winget | choco | scoop | pip | apt | download | manual
    install_command: list[str] = field(default_factory=list)
    health_check: str = ""


class DependencyRegistry:
    """Registry of all dependencies AAiOS knows about."""

    def __init__(self) -> None:
        self._specs: list[DependencySpec] = self._default_specs()

    def list_all(self) -> list[DependencySpec]:
        return list(self._specs)

    def list_required(self) -> list[DependencySpec]:
        return [s for s in self._specs if s.category == "required"]

    def list_recommended(self) -> list[DependencySpec]:
        return [s for s in self._specs if s.category == "recommended"]

    def list_optional(self) -> list[DependencySpec]:
        return [s for s in self._specs if s.category == "optional"]

    def _default_specs(self) -> list[DependencySpec]:
        return [
            # --- Required ---
            DependencySpec(
                name="python",
                category="required",
                tool="python",
                min_version="3.12",
                can_install=True,
                install_method="winget",
                install_command=["winget", "install", "Python.Python.3.12"],
                health_check="python --version",
            ),
            DependencySpec(
                name="git",
                category="required",
                tool="git",
                min_version="2.40",
                can_install=True,
                install_method="winget",
                install_command=["winget", "install", "Git.Git"],
                health_check="git --version",
            ),
            # --- Recommended ---
            DependencySpec(
                name="node",
                category="recommended",
                tool="node",
                min_version="20.0",
                can_install=True,
                install_method="winget",
                install_command=["winget", "install", "OpenJS.NodeJS.LTS"],
                health_check="node --version",
            ),
            DependencySpec(
                name="pnpm",
                category="recommended",
                tool="pnpm",
                min_version="9.0",
                can_install=True,
                install_method="npm",
                install_command=["npm", "install", "-g", "pnpm"],
                health_check="pnpm --version",
            ),
            DependencySpec(
                name="docker",
                category="recommended",
                tool="docker",
                min_version="24.0",
                can_install=True,
                install_method="winget",
                install_command=["winget", "install", "Docker.DockerDesktop"],
                health_check="docker --version",
            ),
            DependencySpec(
                name="sqlite",
                category="recommended",
                tool="sqlite3",
                min_version="3.40",
                can_install=False,
                can_skip=True,
                health_check="sqlite3 --version",
            ),
            DependencySpec(
                name="postgresql",
                category="recommended",
                tool="psql",
                min_version="14.0",
                can_install=True,
                can_skip=True,
                install_method="winget",
                install_command=["winget", "install", "PostgreSQL.PostgreSQL"],
                health_check="psql --version",
            ),
            # --- Optional: Vector store / cache ---
            DependencySpec(
                name="qdrant",
                category="optional",
                tool="qdrant",
                can_install=False,
                can_skip=True,
                health_check="docker ps | grep qdrant",
            ),
            DependencySpec(
                name="redis",
                category="optional",
                tool="redis-cli",
                min_version="6.0",
                can_install=False,
                can_skip=True,
                health_check="redis-cli ping",
            ),
            DependencySpec(
                name="memurai",
                category="optional",
                tool="memurai",
                can_install=False,
                can_skip=True,
                health_check="memurai --version",
            ),
            # --- Optional: Local LLMs ---
            DependencySpec(
                name="ollama",
                category="optional",
                tool="ollama",
                can_install=True,
                can_skip=True,
                install_method="download",
                install_command=["curl", "-fsSL", "https://ollama.com/install.sh"],
                health_check="ollama --version",
            ),
            DependencySpec(
                name="lm-studio",
                category="optional",
                tool="lms",
                can_install=False,
                can_skip=True,
                health_check="lms version",
            ),
            # --- Optional: Coding agents ---
            DependencySpec(
                name="claude-code",
                category="optional",
                tool="claude",
                can_install=False,
                can_skip=True,
                health_check="claude --version",
            ),
            DependencySpec(
                name="opencode",
                category="optional",
                tool="opencode",
                can_install=False,
                can_skip=True,
                health_check="opencode --version",
            ),
            DependencySpec(
                name="codex-cli",
                category="optional",
                tool="codex",
                can_install=False,
                can_skip=True,
                health_check="codex --version",
            ),
            DependencySpec(
                name="gemini-cli",
                category="optional",
                tool="gemini",
                can_install=False,
                can_skip=True,
                health_check="gemini --version",
            ),
            DependencySpec(
                name="openhands",
                category="optional",
                tool="openhands",
                can_install=False,
                can_skip=True,
                health_check="openhands --version",
            ),
            DependencySpec(
                name="cline",
                category="optional",
                tool="cline",
                can_install=False,
                can_skip=True,
                health_check="cline --version",
            ),
            DependencySpec(
                name="roo-code",
                category="optional",
                tool="roo",
                can_install=False,
                can_skip=True,
                health_check="roo --version",
            ),
            # --- Optional: Package managers ---
            DependencySpec(
                name="winget",
                category="optional",
                tool="winget",
                can_install=False,
                can_skip=True,
                health_check="winget --version",
            ),
            DependencySpec(
                name="chocolatey",
                category="optional",
                tool="choco",
                can_install=False,
                can_skip=True,
                health_check="choco --version",
            ),
            DependencySpec(
                name="scoop",
                category="optional",
                tool="scoop",
                can_install=False,
                can_skip=True,
                health_check="scoop --version",
            ),
            DependencySpec(
                name="github-cli",
                category="optional",
                tool="gh",
                can_install=True,
                can_skip=True,
                install_method="winget",
                install_command=["winget", "install", "GitHub.cli"],
                health_check="gh --version",
            ),
            # --- Optional: Runtimes ---
            DependencySpec(
                name="playwright",
                category="optional",
                tool="playwright",
                can_install=True,
                can_skip=True,
                install_method="pip",
                install_command=["pip", "install", "playwright"],
                health_check="playwright --version",
            ),
            DependencySpec(
                name="vc-redist",
                category="optional",
                can_install=False,
                can_skip=True,
                health_check="(check Add/Remove Programs)",
            ),
            DependencySpec(
                name="dotnet-runtime",
                category="optional",
                tool="dotnet",
                can_install=False,
                can_skip=True,
                health_check="dotnet --version",
            ),
            # --- Optional: WSL / Hyper-V (Windows only) ---
            DependencySpec(
                name="wsl",
                category="optional",
                tool="wsl",
                can_install=False,
                can_skip=True,
                health_check="wsl --status",
            ),
            DependencySpec(
                name="hyperv",
                category="optional",
                can_install=False,
                can_skip=True,
                health_check="(Windows optional feature)",
            ),
        ]


class DependencyChecker:
    """Phase 2 — verify every dependency against the host environment."""

    def __init__(self, registry: DependencyRegistry | None = None) -> None:
        self.registry = registry or DependencyRegistry()

    def check_all(self) -> list[DependencyCheck]:
        """Check every dependency in the registry."""
        results: list[DependencyCheck] = []
        for spec in self.registry.list_all():
            results.append(self._check_one(spec))
        return results

    def check_required(self) -> list[DependencyCheck]:
        """Check only required dependencies."""
        return [self._check_one(s) for s in self.registry.list_required()]

    def check_optional(self) -> list[DependencyCheck]:
        """Check only optional dependencies."""
        return [self._check_one(s) for s in self.registry.list_optional()]

    def install_missing(
        self,
        checks: list[DependencyCheck],
        *,
        skip_optional: bool = True,
    ) -> list[DependencyCheck]:
        """Attempt to install missing dependencies.

        Args:
            checks: results from check_all()
            skip_optional: if True, optional dependencies are not auto-installed.

        Returns:
            Updated checks with install_attempted and install_succeeded set.
        """
        updated: list[DependencyCheck] = []
        for check in checks:
            spec = self._find_spec(check.name)
            if not spec:
                updated.append(check)
                continue
            if check.status == DependencyStatus.PRESENT.value:
                updated.append(check)
                continue
            if skip_optional and spec.category == "optional":
                check.status = DependencyStatus.OPTIONAL_SKIPPED.value
                updated.append(check)
                continue
            if not spec.can_install or not spec.install_command:
                if spec.category == "required":
                    check.error = f"Cannot auto-install {spec.name}; {spec.install_hint or 'manual install required'}"
                else:
                    check.status = DependencyStatus.OPTIONAL_SKIPPED.value
                updated.append(check)
                continue
            # Attempt install
            check.install_attempted = True
            try:
                result = subprocess.run(  # noqa: S603
                    spec.install_command,  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                if result.returncode == 0:
                    check.install_succeeded = True
                    check.status = DependencyStatus.INSTALLED.value
                    _log.info("installer.dependency_installed", name=spec.name)
                else:
                    check.error = result.stderr[:200] if result.stderr else "install failed"
                    check.status = DependencyStatus.INSTALL_FAILED.value
                    _log.warning(
                        "installer.dependency_install_failed",
                        name=spec.name,
                        error=check.error,
                    )
            except (subprocess.SubprocessError, OSError) as e:
                check.error = str(e)
                check.status = DependencyStatus.INSTALL_FAILED.value
            updated.append(check)
        return updated

    def _check_one(self, spec: DependencySpec) -> DependencyCheck:
        """Check a single dependency."""
        check = DependencyCheck(
            name=spec.name,
            category=spec.category,
            required_version=spec.min_version,
            can_install=spec.can_install,
            can_skip=spec.can_skip,
        )
        if not spec.tool:
            # No CLI tool to check — mark as unknown
            check.status = DependencyStatus.OPTIONAL_SKIPPED.value
            return check
        path = shutil.which(spec.tool)
        if not path:
            check.status = DependencyStatus.MISSING.value
            return check
        check.install_path = path
        check.in_path = True
        # Get version
        version = self._get_version(path, spec.version_args)
        check.detected_version = version
        if spec.min_version and version:
            if not self._version_gte(version, spec.min_version):
                check.status = DependencyStatus.OUTDATED.value
                check.healthy = False
                return check
        check.status = DependencyStatus.PRESENT.value
        check.healthy = True
        check.health_check_output = f"{spec.tool} found at {path}"
        return check

    def _get_version(self, path: str, args: tuple[str, ...]) -> str:
        try:
            result = subprocess.run(  # noqa: S603
                [path, *args],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.strip():
                        return line.strip()[:100]
            return ""
        except (subprocess.SubprocessError, OSError):
            return ""

    def _version_gte(self, detected: str, required: str) -> bool:
        """Compare two version strings (loose comparison)."""

        def parse(v: str) -> tuple[int, ...]:
            parts = []
            for p in re.findall(r"\d+", v):
                parts.append(int(p))
            return tuple(parts)

        try:
            d = parse(detected)
            r = parse(required)
            # Pad to equal length
            while len(d) < len(r):
                d = (*d, 0)
            while len(r) < len(d):
                r = (*r, 0)
            return d >= r
        except (ValueError, TypeError):
            return True  # If we can't parse, assume OK

    def _find_spec(self, name: str) -> DependencySpec | None:
        for spec in self.registry.list_all():
            if spec.name == name:
                return spec
        return None


# Import re here to avoid circular imports at module load
import re  # noqa: E402
