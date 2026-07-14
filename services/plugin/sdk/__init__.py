"""Plugin SDK — typed interfaces for writing AAiOS plugins.

A plugin is a Python package that provides one or more of:
  - Agents (implement GenericAgent)
  - Tools (register with the Tool Registry)
  - LLM providers (implement ModelProvider Protocol)
  - Dashboard widgets (Phase 12)
  - Memory adapters (implement MemoryStore Protocol)

The SDK provides:
  - PluginManifest builder
  - Base classes for common plugin patterns
  - Registration helpers
  - Test harness utilities

Usage:
    from services.plugin.sdk import PluginManifestBuilder, ToolPlugin

    class WeatherPlugin(ToolPlugin):
        manifest = PluginManifestBuilder('weather', '1.0.0') \\
            .description('Get weather for any city') \\
            .provides_tools(['weather_plugin.get_weather']) \\
            .requires_permissions(['gateway.net.request']) \\
            .build()

        def register_tools(self, registry):
            registry.register(Tool(name='weather.get', handler=get_weather, ...))
"""

from __future__ import annotations

from typing import Any, Protocol

from services.plugin.manager import PluginManifest

__all__ = [
    "AgentPlugin",
    "PluginBase",
    "PluginManifestBuilder",
    "ToolPlugin",
]


class PluginManifestBuilder:
    """Fluent builder for PluginManifest."""

    def __init__(self, name: str, version: str) -> None:
        self._name = name
        self._version = version
        self._description: str = ""
        self._vendor: str = ""
        self._provides_agents: list[str] = []
        self._provides_tools: list[str] = []
        self._provides_providers: list[str] = []
        self._provides_widgets: list[str] = []
        self._requires_permissions: list[str] = []
        self._requires_api_keys: list[str] = []
        self._entry_point: str = ""

    def description(self, desc: str) -> PluginManifestBuilder:
        """Set the description."""
        self._description = desc
        return self

    def vendor(self, v: str) -> PluginManifestBuilder:
        """Set the vendor."""
        self._vendor = v
        return self

    def provides_agents(self, *paths: str) -> PluginManifestBuilder:
        """Declare agent class paths this plugin provides."""
        self._provides_agents.extend(paths)
        return self

    def provides_tools(self, *paths: str) -> PluginManifestBuilder:
        """Declare tool registration callables this plugin provides."""
        self._provides_tools.extend(paths)
        return self

    def provides_providers(self, *paths: str) -> PluginManifestBuilder:
        """Declare LLM provider class paths this plugin provides."""
        self._provides_providers.extend(paths)
        return self

    def provides_widgets(self, *paths: str) -> PluginManifestBuilder:
        """Declare dashboard widget paths this plugin provides."""
        self._provides_widgets.extend(paths)
        return self

    def requires_permissions(self, *perms: str) -> PluginManifestBuilder:
        """Declare permissions this plugin requires."""
        self._requires_permissions.extend(perms)
        return self

    def requires_api_keys(self, *keys: str) -> PluginManifestBuilder:
        """Declare API keys this plugin requires."""
        self._requires_api_keys.extend(keys)
        return self

    def entry_point(self, module: str) -> PluginManifestBuilder:
        """Set the Python module path for the plugin entry point."""
        self._entry_point = module
        return self

    def build(self) -> PluginManifest:
        """Build the manifest."""
        return PluginManifest(
            name=self._name,
            version=self._version,
            description=self._description,
            vendor=self._vendor,
            provides_agents=self._provides_agents,
            provides_tools=self._provides_tools,
            provides_providers=self._provides_providers,
            provides_widgets=self._provides_widgets,
            requires_permissions=self._requires_permissions,
            requires_api_keys=self._requires_api_keys,
            entry_point=self._entry_point or self._name,
        )


class PluginBase(Protocol):
    """Base interface for all plugins.

    A plugin package must expose a ``Plugin`` class that implements this
    interface. The Plugin Manager calls ``on_load()`` when enabling and
    ``on_unload()`` when disabling.
    """

    manifest: PluginManifest

    async def on_load(self, context: Any) -> None:
        """Called when the plugin is loaded. Register resources here."""
        ...

    async def on_unload(self) -> None:
        """Called when the plugin is unloaded. Clean up resources here."""
        ...


class ToolPlugin:
    """Convenience base class for plugins that only provide tools.

    Subclasses implement ``register_tools(registry)`` and the Plugin
    Manager calls it on load.
    """

    manifest: PluginManifest

    async def on_load(self, context: Any) -> None:
        """Load: register tools."""
        registry = getattr(context, "tool_registry", None)
        if registry is not None:
            self.register_tools(registry)

    async def on_unload(self) -> None:
        """Unload: no-op (tools are unregistered by the Plugin Manager)."""
        pass

    def register_tools(self, registry: Any) -> None:
        """Override to register tools. Called by ``on_load``."""
        raise NotImplementedError


class AgentPlugin:
    """Convenience base class for plugins that provide agents.

    Subclasses implement ``create_agents()`` which returns a list of
    GenericAgent instances. The Plugin Manager registers them in the
    Agent Registry on load.
    """

    manifest: PluginManifest

    async def on_load(self, context: Any) -> None:
        """Load: register agents."""
        registry = getattr(context, "agent_registry", None)
        if registry is not None:
            for agent in self.create_agents():
                await registry.register(agent)

    async def on_unload(self) -> None:
        """Unload: no-op (agents are unregistered by the Plugin Manager)."""
        pass

    def create_agents(self) -> list[Any]:
        """Override to create agent instances. Called by ``on_load``."""
        raise NotImplementedError
