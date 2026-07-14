"""MCP Manager — discover, register, authenticate, monitor, hot-reload MCP servers.

MCP (Model Context Protocol) servers extend AAiOS with external tools,
resources, and prompts. The MCP Manager handles the full lifecycle.
"""

from __future__ import annotations

from services.mcp.manager import (
    MCPManager,
    MCPServerConfig,
    MCPServerInfo,
    MCPServerState,
)

__all__ = [
    "MCPManager",
    "MCPServerConfig",
    "MCPServerInfo",
    "MCPServerState",
]
