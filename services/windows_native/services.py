"""Windows Services Manager — install/start/stop/query Windows Services.

On Windows, uses the `sc.exe` and `powershell.exe Get-Service` commands.
On non-Windows, all methods return structured "unsupported" results so
the rest of the system can be developed and tested on Linux/WSL.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "ServiceAlreadyExistsError",
    "ServiceConfig",
    "ServiceNotFoundError",
    "ServiceState",
    "ServiceStatus",
    "WindowsServicesManager",
]


class ServiceNotFoundError(Exception):
    """Raised when a service name is not registered."""


class ServiceAlreadyExistsError(Exception):
    """Raised when attempting to create a service that already exists."""


@dataclass
class ServiceConfig:
    """Configuration for a Windows Service.

    bin_path: absolute path to the executable (e.g. C:\\AAiOS\\agent.exe)
    display_name: human-readable name shown in services.msc
    description: longer description
    start_type: 'auto' | 'manual' | 'disabled'
    account: account to run as (e.g. 'LocalSystem', 'NT AUTHORITY\\NetworkService')
    password: account password (None for built-in accounts)
    """

    bin_path: str
    display_name: str
    description: str = ""
    start_type: str = "auto"  # auto, manual, disabled
    account: str = "LocalSystem"
    password: str | None = None
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bin_path": self.bin_path,
            "display_name": self.display_name,
            "description": self.description,
            "start_type": self.start_type,
            "account": self.account,
            "dependencies": list(self.dependencies),
        }


class ServiceState:
    """Service state constants."""

    STOPPED = "stopped"
    START_PENDING = "start_pending"
    RUNNING = "running"
    STOP_PENDING = "stop_pending"
    PAUSED = "paused"
    UNKNOWN = "unknown"


@dataclass
class ServiceStatus:
    """Status of a Windows Service."""

    name: str
    display_name: str
    state: str
    pid: int | None = None
    start_type: str = "auto"
    can_stop: bool = False
    can_pause: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "state": self.state,
            "pid": self.pid,
            "start_type": self.start_type,
            "can_stop": self.can_stop,
            "can_pause": self.can_pause,
        }


class WindowsServicesManager:
    """Manage Windows Services via `sc.exe` and PowerShell.

    On non-Windows platforms, every method returns a structured "unsupported"
    result with state='unknown' so the rest of the system remains testable.
    """

    def __init__(self, *, dry_run: bool = False) -> None:
        self._is_windows = sys.platform == "win32"
        self._dry_run = dry_run or not self._is_windows

    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        """Run a command, return (returncode, stdout, stderr)."""
        if self._dry_run:
            return 0, "", ""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        return proc.returncode or 0, stdout_b.decode(), stderr_b.decode()

    async def create(
        self,
        name: str,
        config: ServiceConfig,
    ) -> ServiceStatus:
        """Install a new Windows Service."""
        if not self._is_windows:
            _log.warning(
                "Windows Services not supported on %s; returning stub for '%s'",
                sys.platform,
                name,
            )
            return ServiceStatus(
                name=name,
                display_name=config.display_name,
                state=ServiceState.UNKNOWN,
                start_type=config.start_type,
            )
        # Check if it exists
        existing = await self.query(name)
        if existing.state not in (ServiceState.UNKNOWN, ""):
            raise ServiceAlreadyExistsError(f"Service '{name}' already exists")
        start_map = {"auto": "auto", "manual": "demand", "disabled": "disabled"}
        sc_start = start_map.get(config.start_type, "auto")
        args = [
            "sc.exe",
            "create",
            name,
            f"binPath={config.bin_path}",
            f"DisplayName={config.display_name}",
            f"start={sc_start}",
            f"obj={config.account}",
        ]
        if config.dependencies:
            args.append(f"depend={'+'.join(config.dependencies)}")
        rc, out, err = await self._run(args)
        if rc != 0:
            raise RuntimeError(f"sc.exe create failed: {err or out}")
        # Set description
        if config.description:
            await self._run(
                ["sc.exe", "description", name, config.description],
            )
        _log.info("Created Windows Service '%s' (binPath=%s)", name, config.bin_path)
        return await self.query(name)

    async def delete(self, name: str) -> bool:
        """Delete a Windows Service."""
        if not self._is_windows:
            return True
        rc, _, err = await self._run(["sc.exe", "delete", name])
        if rc != 0:
            _log.warning("Failed to delete service '%s': %s", name, err)
            return False
        return True

    async def start(self, name: str) -> bool:
        """Start a service."""
        if not self._is_windows:
            return True
        rc, _, err = await self._run(["sc.exe", "start", name])
        if rc != 0:
            _log.warning("Failed to start service '%s': %s", name, err)
            return False
        return True

    async def stop(self, name: str) -> bool:
        """Stop a service."""
        if not self._is_windows:
            return True
        rc, _, err = await self._run(["sc.exe", "stop", name])
        if rc != 0:
            _log.warning("Failed to stop service '%s': %s", name, err)
            return False
        return True

    async def pause(self, name: str) -> bool:
        """Pause a service."""
        if not self._is_windows:
            return True
        rc, _, _ = await self._run(["sc.exe", "pause", name])
        return rc == 0

    async def continue_(self, name: str) -> bool:
        """Continue a paused service."""
        if not self._is_windows:
            return True
        rc, _, _ = await self._run(["sc.exe", "continue", name])
        return rc == 0

    async def query(self, name: str) -> ServiceStatus:
        """Query a service's status."""
        if not self._is_windows:
            return ServiceStatus(
                name=name,
                display_name=name,
                state=ServiceState.UNKNOWN,
            )
        rc, out, _ = await self._run(["sc.exe", "query", name])
        if rc != 0:
            return ServiceStatus(
                name=name,
                display_name=name,
                state=ServiceState.UNKNOWN,
            )
        state = ServiceState.UNKNOWN
        pid: int | None = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("STATE"):
                # STATE : 4 RUNNING (stopable, ...)
                parts = line.split()
                if len(parts) >= 3:
                    state_code = parts[2].lower()
                    state = {
                        "1": ServiceState.STOPPED,
                        "2": ServiceState.START_PENDING,
                        "3": ServiceState.STOP_PENDING,
                        "4": ServiceState.RUNNING,
                        "5": ServiceState.CONTINUE_PENDING if False else ServiceState.PAUSED,
                        "6": ServiceState.PAUSED,
                        "7": ServiceState.UNKNOWN,
                    }.get(state_code, ServiceState.UNKNOWN)
            if line.startswith("PID"):
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        pid = int(parts[2])
                    except ValueError:
                        pass
        # Get display name
        _, out_dn, _ = await self._run(["sc.exe", "query", name, "DisplayName"])
        display_name = name
        for line in out_dn.splitlines():
            line = line.strip()
            if line.startswith("DISPLAY_NAME"):
                display_name = line.split(":", 1)[1].strip()
                break
        return ServiceStatus(
            name=name,
            display_name=display_name,
            state=state,
            pid=pid,
        )

    async def list(self) -> list[ServiceStatus]:
        """List all services (filtered by AAiOS prefix if desired)."""
        if not self._is_windows:
            return []
        rc, out, _ = await self._run(["sc.exe", "query", "type=", "service", "state=", "all"])
        if rc != 0:
            return []
        services: list[ServiceStatus] = []
        current_name = ""
        current_state = ServiceState.UNKNOWN
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("SERVICE_NAME"):
                if current_name:
                    services.append(
                        ServiceStatus(
                            name=current_name,
                            display_name=current_name,
                            state=current_state,
                        ),
                    )
                current_name = line.split(":", 1)[1].strip()
            elif line.startswith("STATE"):
                parts = line.split()
                if len(parts) >= 3:
                    code = parts[2]
                    current_state = {
                        "1": ServiceState.STOPPED,
                        "4": ServiceState.RUNNING,
                    }.get(code, ServiceState.UNKNOWN)
        if current_name:
            services.append(
                ServiceStatus(
                    name=current_name,
                    display_name=current_name,
                    state=current_state,
                ),
            )
        return services
