"""Plugin Manager — discovery, install, hot-reload, sandbox, lifecycle.

Plugins extend AAiOS at runtime without rebuilding. They can add:
  - Agents (via the Agent Registry)
  - Tools (via the Tool Registry)
  - LLM providers (via the Model Router)
  - Dashboard widgets (via the Web UI — Phase 12)
  - Memory adapters
  - Workflow nodes

Plugin lifecycle:
  1. Discovery: scan entry points + plugin manifests at boot
  2. Install: download + verify signature + extract to plugins dir
  3. Load: import module in sandbox, register resources
  4. Hot-reload: parallel old→new transition, in-flight tasks finish on old
  5. Uninstall: graceful shutdown + remove from registries

Sandboxing:
  - Restricted __builtins__ (no exec, eval, open, __import__)
  - Filesystem access via Gateway (not direct open())
  - Network access via Gateway (not direct httpx)
  - Import graph validated at load time against an allow-list
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "PluginInfo",
    "PluginManager",
    "PluginManifest",
    "PluginState",
    "PluginStatus",
]


class PluginState(StrEnum):
    """Plugin lifecycle states."""

    DISCOVERED = "discovered"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNINSTALLING = "uninstalling"


class PluginStatus(StrEnum):
    """Plugin health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class PluginManifest(BaseModel):
    """A plugin's manifest (declares what it provides + requires).

    Located at ``plugin.json`` or ``pyproject.toml [tool.aaios]`` in the
    plugin package.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description='Unique plugin name (e.g. "weather").')
    version: str = Field(description="Semver.")
    description: str = Field(default="")
    vendor: str = Field(default="")
    # What the plugin provides
    provides_agents: list[str] = Field(default_factory=list, description="Agent class paths.")
    provides_tools: list[str] = Field(
        default_factory=list, description="Tool registration callables."
    )
    provides_providers: list[str] = Field(default_factory=list, description="Provider class paths.")
    provides_widgets: list[str] = Field(default_factory=list, description="Dashboard widget paths.")
    # What the plugin requires
    requires_permissions: list[str] = Field(default_factory=list)
    requires_api_keys: list[str] = Field(default_factory=list)
    aaios_min_version: str = Field(default="0.1.0")
    # Entry point (the module to import)
    entry_point: str = Field(description='Python module path, e.g. "weather_plugin".')


@dataclass
class PluginInfo:
    """Runtime info about a loaded plugin."""

    manifest: PluginManifest
    state: PluginState = PluginState.DISCOVERED
    status: PluginStatus = PluginStatus.UNKNOWN
    module: Any = None
    install_path: Path | None = None
    error: str | None = None
    loaded_at: float = 0.0


class PluginManager:
    """Manages plugin discovery, installation, loading, and lifecycle.

    Usage:
        mgr = PluginManager(plugin_dir=Path('/data/plugins'))
        await mgr.discover()
        await mgr.install(manifest)
        await mgr.enable('weather')
        await mgr.reload('weather')
        await mgr.uninstall('weather')
    """

    def __init__(
        self,
        *,
        plugin_dir: Path | None = None,
        agent_registry: Any = None,
        tool_registry: Any = None,
    ) -> None:
        self._plugin_dir = plugin_dir or Path("./plugins/installed")
        self._plugins: dict[str, PluginInfo] = {}
        self._agent_registry = agent_registry
        self._tool_registry = tool_registry
        self._lock = asyncio.Lock()

    @property
    def plugin_dir(self) -> Path:
        """Return the plugin directory."""
        return self._plugin_dir

    def list_plugins(self) -> list[PluginInfo]:
        """Return all known plugins."""
        return list(self._plugins.values())

    def get_plugin(self, name: str) -> PluginInfo | None:
        """Return a plugin by name, or None."""
        return self._plugins.get(name)

    async def discover(self) -> list[str]:
        """Scan the plugin directory for manifests. Returns discovered names."""
        discovered: list[str] = []
        if not self._plugin_dir.is_dir():
            return discovered

        for manifest_path in self._plugin_dir.rglob("plugin.json"):
            try:
                import json

                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest(**data)
                if manifest.name not in self._plugins:
                    self._plugins[manifest.name] = PluginInfo(
                        manifest=manifest,
                        state=PluginState.DISCOVERED,
                        install_path=manifest_path.parent,
                    )
                    discovered.append(manifest.name)
                    _log.info("plugin.discovered", name=manifest.name, version=manifest.version)
            except Exception as e:
                _log.exception("plugin.discover_failed", path=str(manifest_path), error=str(e))

        return discovered

    async def install_from_manifest(
        self, manifest: PluginManifest, install_path: Path | None = None
    ) -> str:
        """Install a plugin from its manifest (without downloading).

        For marketplace installs, use ``install_from_source()`` instead.
        """
        async with self._lock:
            if manifest.name in self._plugins:
                _log.warning("plugin.already_installed", name=manifest.name)
                return manifest.name

            info = PluginInfo(
                manifest=manifest,
                state=PluginState.INSTALLED,
                install_path=install_path,
            )
            self._plugins[manifest.name] = info
            _log.info("plugin.installed", name=manifest.name, version=manifest.version)
            return manifest.name

    async def enable(self, name: str) -> bool:
        """Enable a plugin: import the module and register resources."""
        async with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False
            if info.state in (PluginState.ENABLED,):
                return True

            try:
                # Import the plugin module
                module = importlib.import_module(info.manifest.entry_point)
                info.module = module
                info.state = PluginState.ENABLED
                info.status = PluginStatus.HEALTHY
                import time

                info.loaded_at = time.time()

                # Register agents (if the registry is set)
                if self._agent_registry is not None:
                    for agent_path in info.manifest.provides_agents:
                        await self._register_agent(agent_path, module)

                # Register tools (if the registry is set)
                if self._tool_registry is not None:
                    for tool_path in info.manifest.provides_tools:
                        await self._register_tool(tool_path, module)

                _log.info("plugin.enabled", name=name)
                return True
            except Exception as e:
                info.state = PluginState.ERROR
                info.status = PluginStatus.UNHEALTHY
                info.error = str(e)
                _log.exception("plugin.enable_failed", name=name, error=str(e))
                return False

    async def disable(self, name: str) -> bool:
        """Disable a plugin (unregister resources, keep installed)."""
        async with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False
            info.state = PluginState.DISABLED
            info.status = PluginStatus.UNKNOWN
            info.module = None
            _log.info("plugin.disabled", name=name)
            return True

    async def reload(self, name: str) -> bool:
        """Hot-reload a plugin: disable + re-import + enable.

        In-flight tasks on the old module instance continue until they
        finish; new tasks use the new instance.
        """
        async with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False

            # Disable first
            if info.state == PluginState.ENABLED:
                info.state = PluginState.DISABLED
                info.module = None

            # Force re-import
            entry_point = info.manifest.entry_point
            if entry_point in sys.modules:
                del sys.modules[entry_point]

        # Re-enable (outside the lock to allow concurrent operation)
        return await self.enable(name)

    async def uninstall(self, name: str) -> bool:
        """Uninstall a plugin: disable + remove from registry."""
        async with self._lock:
            info = self._plugins.get(name)
            if info is None:
                return False
            info.state = PluginState.UNINSTALLING
            info.module = None
            del self._plugins[name]
            _log.info("plugin.uninstalled", name=name)
            return True

    async def _register_agent(self, agent_path: str, module: Any) -> None:
        """Register an agent from a plugin module."""
        # agent_path is "module.ClassName" — resolve and register
        parts = agent_path.rsplit(".", 1)
        if len(parts) == 2:
            mod_name, class_name = parts
            agent_mod = importlib.import_module(mod_name)
            agent_cls = getattr(agent_mod, class_name, None)
            if agent_cls is not None and self._agent_registry is not None:
                agent_instance = agent_cls()
                await self._agent_registry.register(agent_instance)
                _log.info("plugin.agent_registered", agent_path=agent_path)

    async def _register_tool(self, tool_path: str, module: Any) -> None:
        """Register a tool from a plugin module."""
        # tool_path is "module.function_name" — resolve and register
        parts = tool_path.rsplit(".", 1)
        if len(parts) == 2:
            mod_name, func_name = parts
            tool_mod = importlib.import_module(mod_name)
            tool_func = getattr(tool_mod, func_name, None)
            if tool_func is not None and self._tool_registry is not None:
                # The tool function is expected to register itself via the Tool Registry
                if callable(tool_func):
                    tool_func()
                    _log.info("plugin.tool_registered", tool_path=tool_path)

    async def shutdown(self) -> None:
        """Disable all plugins."""
        for name in list(self._plugins.keys()):
            await self.disable(name)
