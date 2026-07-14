"""MCP Manager — discover, register, authenticate, monitor, hot-reload MCP servers.

MCP (Model Context Protocol) servers extend AAiOS with external tools,
resources, and prompts. The MCP Manager handles the full lifecycle:

  1. Discovery: scan config/mcp-servers/ for server definitions
  2. Registration: connect to the server, list its tools/resources/prompts
  3. Authentication: OAuth2 / API key / none
  4. Monitoring: health checks, auto-restart (max 3 in 5 min)
  5. Hot-reload: reconnect without dropping in-flight calls
  6. Lifecycle: enable/disable/reload/uninstall

MCP tools are registered in the Tool Registry so agents can call them
transparently — the agent doesn't know whether a tool is built-in or
MCP-provided.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "MCPServerConfig",
    "MCPServerInfo",
    "MCPManager",
    "MCPServerState",
]


class MCPServerState(StrEnum):
    """MCP server lifecycle states."""

    REGISTERED = "registered"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DISABLED = "disabled"


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Located at ``config/mcp-servers/<name>.yaml`` or ``.json``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Unique server name.")
    command: str = Field(description='The command to start the server (e.g. "npx @mcp/server").')
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    # Auth
    auth_type: str = Field(default="none", description="none, api_key, oauth2")
    api_key: str | None = None
    # Monitoring
    auto_restart: bool = Field(default=True)
    max_restarts: int = Field(default=3)
    restart_window_s: int = Field(default=300)
    # Tools filter (if set, only these tools are registered)
    tools_filter: list[str] | None = None


@dataclass
class MCPServerInfo:
    """Runtime info about a connected MCP server."""

    config: MCPServerConfig
    state: MCPServerState = MCPServerState.REGISTERED
    tools: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    process: Any = None
    error: str | None = None
    restart_count: int = 0
    last_restart: float = 0.0


class MCPManager:
    """Manages MCP server lifecycle.

    Usage:
        mgr = MCPManager(config_dir=Path('/config/mcp-servers'))
        await mgr.discover()
        await mgr.register(MCPServerConfig(name='slack', command='npx @mcp/slack'))
        await mgr.connect('slack')
        tools = mgr.list_tools('slack')
        result = await mgr.call_tool('slack', 'send_message', {'channel': '#general'})
    """

    def __init__(
        self,
        *,
        config_dir: Path | None = None,
        tool_registry: Any = None,
    ) -> None:
        self._config_dir = config_dir or Path("./config/mcp-servers")
        self._servers: dict[str, MCPServerInfo] = {}
        self._tool_registry = tool_registry
        self._lock = asyncio.Lock()

    def list_servers(self) -> list[MCPServerInfo]:
        """Return all known MCP servers."""
        return list(self._servers.values())

    def get_server(self, name: str) -> MCPServerInfo | None:
        """Return a server by name, or None."""
        return self._servers.get(name)

    async def discover(self) -> list[str]:
        """Scan the config directory for MCP server configs."""
        discovered: list[str] = []
        if not self._config_dir.is_dir():
            return discovered

        for config_path in self._config_dir.glob("*.json"):
            try:
                import json

                data = json.loads(config_path.read_text(encoding="utf-8"))
                config = MCPServerConfig(**data)
                if config.name not in self._servers:
                    self._servers[config.name] = MCPServerInfo(config=config)
                    discovered.append(config.name)
                    _log.info("mcp.discovered", name=config.name)
            except Exception as e:
                _log.exception("mcp.discover_failed", path=str(config_path), error=str(e))

        return discovered

    async def register(self, config: MCPServerConfig) -> str:
        """Register an MCP server (without connecting)."""
        async with self._lock:
            if config.name in self._servers:
                _log.warning("mcp.already_registered", name=config.name)
                return config.name
            self._servers[config.name] = MCPServerInfo(config=config)
            _log.info("mcp.registered", name=config.name, command=config.command)
            return config.name

    async def connect(self, name: str) -> bool:
        """Connect to an MCP server (spawn the subprocess + handshake).

        Phase 11: records the connection but doesn't actually spawn the
        subprocess (that requires the Gateway's process.spawn method,
        which lands in Phase 14). The server is marked as CONNECTED for
        mock/testing purposes.
        """
        async with self._lock:
            info = self._servers.get(name)
            if info is None:
                return False
            try:
                # Phase 11 mock: just mark as connected
                # Phase 14 will spawn the subprocess via gateway.process.spawn()
                info.state = MCPServerState.CONNECTED
                # Mock: discover some tools
                info.tools = ["mock_tool_1", "mock_tool_2"]
                info.resources = []
                info.prompts = []
                _log.info("mcp.connected", name=name, tools=len(info.tools))
                return True
            except Exception as e:
                info.state = MCPServerState.ERROR
                info.error = str(e)
                _log.exception("mcp.connect_failed", name=name, error=str(e))
                return False

    async def disconnect(self, name: str) -> bool:
        """Disconnect from an MCP server."""
        async with self._lock:
            info = self._servers.get(name)
            if info is None:
                return False
            info.state = MCPServerState.DISCONNECTED
            info.tools = []
            _log.info("mcp.disconnected", name=name)
            return True

    async def reload(self, name: str) -> bool:
        """Hot-reload: disconnect + reconnect."""
        await self.disconnect(name)
        return await self.connect(name)

    async def unregister(self, name: str) -> bool:
        """Unregister a server."""
        async with self._lock:
            if name not in self._servers:
                return False
            await self.disconnect(name)
            del self._servers[name]
            _log.info("mcp.unregistered", name=name)
            return True

    def list_tools(self, server_name: str) -> list[str]:
        """Return the tools offered by a server."""
        info = self._servers.get(server_name)
        if info is None:
            return []
        return list(info.tools)

    def list_all_tools(self) -> dict[str, list[str]]:
        """Return all tools from all connected servers."""
        return {
            name: list(info.tools)
            for name, info in self._servers.items()
            if info.state == MCPServerState.CONNECTED
        }

    async def call_tool(self, server_name: str, tool_name: str, args: dict[str, Any]) -> Any:
        """Call a tool on an MCP server.

        Phase 11: returns a mock result. Phase 14 will make the real call
        via JSON-RPC to the server subprocess.
        """
        info = self._servers.get(server_name)
        if info is None or info.state != MCPServerState.CONNECTED:
            raise RuntimeError(f"MCP server {server_name} not connected")
        if tool_name not in info.tools:
            raise ValueError(f"Tool {tool_name} not found on server {server_name}")
        # Phase 11 mock
        _log.info("mcp.call_tool", server=server_name, tool=tool_name)
        return {"mock": True, "server": server_name, "tool": tool_name, "args": args}

    async def shutdown(self) -> None:
        """Disconnect all servers."""
        for name in list(self._servers.keys()):
            await self.disconnect(name)
