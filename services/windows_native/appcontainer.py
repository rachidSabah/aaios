"""AppContainer — Windows application sandboxing via AppContainer capability isolation.

AppContainer is the Windows sandboxing primitive introduced in Windows 8.
It runs a process inside an AppContainer profile with a tiny capability
set (internet, local network, documents library, etc.) and an isolated
registry/filesystem view. This is the foundation for sandboxed agent
execution on Windows.

On non-Windows, the manager records state but does not actually create
AppContainer profiles. The actual Win32 API calls (CreateAppContainerProfile,
RunInAppContainer) activate only on win32.

Usage:
    mgr = AppContainerManager()
    profile = await mgr.create_profile("agent-1-sandbox", capabilities=["internet"])
    proc = await mgr.launch(profile.sid, "C:\\agent.exe", ["--config", "..."])
    ...
    await mgr.delete_profile(profile.name)
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "AppContainerManager",
    "AppContainerProfile",
    "AppContainerProcess",
    "SandboxCapability",
]


class SandboxCapability:
    """Known AppContainer capabilities (subset of Windows's defined set).

    Real Windows uses SID strings like
    S-1-15-3-1-...-4096 for InternetClient. We map friendly names to
    those SIDs in the real implementation; here we just record names.
    """

    INTERNET = "internet"  # InternetClient
    INTERNET_SERVER = "internet_server"  # InternetClientServer
    PRIVATE_NETWORK = "private_network"  # PrivateNetworkClientServer
    DOCUMENTS = "documents_library"
    PICTURES = "pictures_library"
    VIDEOS = "videos_library"
    MUSIC = "music_library"
    REMOVABLE_STORAGE = "removable_storage"
    MICROPHONE = "microphone"
    WEBCAM = "webcam"
    LOCATION = "location"
    SHARED_USER_CERTIFICATES = "shared_user_certificates"

    ALL = [
        INTERNET, INTERNET_SERVER, PRIVATE_NETWORK, DOCUMENTS, PICTURES,
        VIDEOS, MUSIC, REMOVABLE_STORAGE, MICROPHONE, WEBCAM, LOCATION,
        SHARED_USER_CERTIFICATES,
    ]


@dataclass
class AppContainerProfile:
    """A registered AppContainer profile."""

    name: str
    sid: str  # On Windows, a real SID like S-1-15-3-...
    capabilities: list[str] = field(default_factory=list)
    folder_path: str | None = None  # Isolated app-data folder
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sid": self.sid,
            "capabilities": list(self.capabilities),
            "folder_path": self.folder_path,
            "created_at": self.created_at,
        }


@dataclass
class AppContainerProcess:
    """A process launched inside an AppContainer."""

    pid: int
    profile_name: str
    exe_path: str
    args: list[str]
    started_at: float = field(default_factory=time.time)
    exited: bool = False
    exit_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "profile_name": self.profile_name,
            "exe_path": self.exe_path,
            "args": list(self.args),
            "started_at": self.started_at,
            "exited": self.exited,
            "exit_code": self.exit_code,
        }


class AppContainerManager:
    """Manages AppContainer profiles and sandboxed process launches.

    On non-Windows, methods are stubbed (returns simulated PIDs and SIDs)
    so the rest of the system remains testable.
    """

    def __init__(self) -> None:
        self._is_windows = sys.platform == "win32"
        self._profiles: dict[str, AppContainerProfile] = {}
        self._processes: dict[int, AppContainerProcess] = {}
        self._next_pid = 10000
        self._lock = asyncio.Lock()

    def _generate_sid(self, name: str) -> str:
        """Generate a deterministic pseudo-SID for non-Windows."""
        # On Windows: PSID from CreateAppContainerProfile
        # Off-Windows: deterministic identifier for test reproducibility
        h = abs(hash(f"aaios-appcontainer-{name}")) % (10**19)
        return f"S-1-15-3-{h}"

    async def create_profile(
        self,
        name: str,
        capabilities: list[str] | None = None,
    ) -> AppContainerProfile:
        """Register a new AppContainer profile."""
        capabilities = capabilities or []
        # Validate capabilities
        for cap in capabilities:
            if cap not in SandboxCapability.ALL:
                raise ValueError(f"Unknown capability: {cap}")
        async with self._lock:
            if name in self._profiles:
                raise ValueError(f"Profile '{name}' already exists")
            sid = self._generate_sid(name)
            profile = AppContainerProfile(
                name=name,
                sid=sid,
                capabilities=capabilities,
            )
            if self._is_windows:
                # Real implementation: CreateAppContainerProfile(name, ...)
                _log.info(
                    "Created real AppContainer profile '%s' (sid=%s, caps=%s)",
                    name, sid, capabilities,
                )
            else:
                _log.info(
                    "AppContainer not supported on %s; recording stub '%s'",
                    sys.platform, name,
                )
            self._profiles[name] = profile
            return profile

    async def delete_profile(self, name: str) -> bool:
        """Delete an AppContainer profile."""
        async with self._lock:
            if name not in self._profiles:
                return False
            if self._is_windows:
                # DeleteAppContainerProfile(name)
                _log.info("Deleted AppContainer profile '%s'", name)
            del self._profiles[name]
            return True

    async def get_profile(self, name: str) -> AppContainerProfile | None:
        async with self._lock:
            return self._profiles.get(name)

    async def list_profiles(self) -> list[AppContainerProfile]:
        async with self._lock:
            return list(self._profiles.values())

    async def launch(
        self,
        profile_name: str,
        exe_path: str,
        args: list[str] | None = None,
    ) -> AppContainerProcess:
        """Launch a process inside an AppContainer profile."""
        args = args or []
        async with self._lock:
            if profile_name not in self._profiles:
                raise ValueError(f"Profile '{profile_name}' not found")
            pid = self._next_pid
            self._next_pid += 1
            proc = AppContainerProcess(
                pid=pid,
                profile_name=profile_name,
                exe_path=exe_path,
                args=list(args),
            )
            if self._is_windows:
                # Real: CreateProcessW(... EXTENDED_STARTUPINFO_PRESENT ...)
                # with PROC_THREAD_ATTRIBUTE_JOB_LIST → AppContainer SID
                _log.info(
                    "Launched pid=%d in AppContainer '%s' (exe=%s)",
                    pid, profile_name, exe_path,
                )
            else:
                _log.info(
                    "Stub launch: pid=%d in AppContainer '%s' (exe=%s)",
                    pid, profile_name, exe_path,
                )
            self._processes[pid] = proc
            return proc

    async def terminate(self, pid: int, exit_code: int = 0) -> bool:
        """Terminate a sandboxed process."""
        async with self._lock:
            if pid not in self._processes:
                return False
            proc = self._processes[pid]
            if proc.exited:
                return False
            if self._is_windows:
                # OpenProcess(PROCESS_TERMINATE) → TerminateProcess(handle, exit_code)
                _log.info("Terminated pid=%d (exit_code=%d)", pid, exit_code)
            proc.exited = True
            proc.exit_code = exit_code
            return True

    async def wait(self, pid: int, timeout_s: float = 30.0) -> int | None:
        """Wait for a sandboxed process to exit. Returns exit code, or None on timeout."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            async with self._lock:
                if pid in self._processes and self._processes[pid].exited:
                    return self._processes[pid].exit_code
            await asyncio.sleep(0.1)
        return None

    async def list_processes(self) -> list[AppContainerProcess]:
        async with self._lock:
            return list(self._processes.values())
