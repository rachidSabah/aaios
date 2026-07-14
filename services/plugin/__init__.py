"""Plugin Manager — discovery, install, hot-reload, sandbox, lifecycle.

Plugins extend AAiOS at runtime without rebuilding. They can add agents,
tools, providers, dashboard widgets, memory adapters, and workflow nodes.
"""

from __future__ import annotations

from services.plugin.manager import (
    PluginInfo,
    PluginManager,
    PluginManifest,
    PluginState,
    PluginStatus,
)

__all__ = [
    "PluginInfo",
    "PluginManager",
    "PluginManifest",
    "PluginState",
    "PluginStatus",
]
