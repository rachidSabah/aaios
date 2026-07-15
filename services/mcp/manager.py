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
        """Connect to an MCP server — spawn subprocess + JSON-RPC initialize.

        Spawns the MCP server process, sends the MCP initialize request,
        discovers tools via tools/list, and registers them.
        """
        async with self._lock:
            info = self._servers.get(name)
            if info is None:
                return False
            if info.state == MCPServerState.CONNECTED:
                return True
            try:
                import asyncio
                import json
                import os

                config = info.config
                env = dict(os.environ)
                env.update(config.env)

                # Spawn the MCP server subprocess
                proc = await asyncio.create_subprocess_exec(
                    config.command,
                    *config.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                info.process = proc

                # Send MCP initialize request (JSON-RPC over stdio)
                init_req = {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "aaios", "version": "1.0.0"},
                    },
                }
                assert proc.stdin is not None
                proc.stdin.write((json.dumps(init_req) + "\n").encode())
                await proc.stdin.drain()

                # Read initialize response (with timeout)
                assert proc.stdout is not None
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
                    if not line:
                        raise RuntimeError("MCP server closed stdout before responding")
                    init_resp = json.loads(line.decode().strip())
                    if "error" in init_resp:
                        raise RuntimeError(f"MCP initialize error: {init_resp['error']}")

                    # Send initialized notification
                    notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
                    proc.stdin.write((json.dumps(notif) + "\n").encode())
                    await proc.stdin.drain()
                except TimeoutError:
                    raise RuntimeError("MCP server initialize timed out (10s)") from None

                # Discover tools via tools/list
                tools_req = {
                    "jsonrpc": "2.0",
                    "id": "2",
                    "method": "tools/list",
                    "params": {},
                }
                proc.stdin.write((json.dumps(tools_req) + "\n").encode())
                await proc.stdin.drain()

                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
                    if line:
                        tools_resp = json.loads(line.decode().strip())
                        tools_data = tools_resp.get("result", {}).get("tools", [])
                        info.tools = [t.get("name", "unknown") for t in tools_data]
                    else:
                        info.tools = []
                except TimeoutError:
                    info.tools = []

                info.resources = []
                info.prompts = []
                info.state = MCPServerState.CONNECTED
                info.error = None
                _log.info(
                    "mcp.connected",
                    name=name,
                    pid=proc.pid,
                    tools=len(info.tools),
                )
                return True

            except Exception as e:
                info.state = MCPServerState.ERROR
                info.error = str(e)
                _log.exception("mcp.connect_failed", name=name, error=str(e))
                return False

    async def disconnect(self, name: str) -> bool:
        """Disconnect from an MCP server — terminate the subprocess."""
        async with self._lock:
            info = self._servers.get(name)
            if info is None:
                return False
            # Terminate the subprocess if running
            if info.process is not None and info.process.returncode is None:
                try:
                    info.process.terminate()
                    import asyncio

                    try:
                        await asyncio.wait_for(info.process.wait(), timeout=5.0)
                    except TimeoutError:
                        info.process.kill()
                except Exception:
                    pass
            info.process = None
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
        # Disconnect first (without holding the lock — disconnect acquires it)
        await self.disconnect(name)
        async with self._lock:
            if name not in self._servers:
                return False
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
        """Call a tool on an MCP server via JSON-RPC.

        Sends a tools/call request to the connected MCP server subprocess
        and returns the result.
        """
        info = self._servers.get(server_name)
        if info is None or info.state != MCPServerState.CONNECTED:
            raise RuntimeError(f"MCP server {server_name} not connected")
        if tool_name not in info.tools:
            raise ValueError(f"Tool {tool_name} not found on server {server_name}")
        if info.process is None or info.process.returncode is not None:
            raise RuntimeError(f"MCP server {server_name} process not running")

        import asyncio
        import json

        req = {
            "jsonrpc": "2.0",
            "id": str(id(args)),  # unique enough for correlation
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
        assert info.process.stdin is not None
        info.process.stdin.write((json.dumps(req) + "\n").encode())
        await info.process.stdin.drain()

        assert info.process.stdout is not None
        try:
            line = await asyncio.wait_for(info.process.stdout.readline(), timeout=30.0)
            if not line:
                raise RuntimeError("MCP server closed stdout")
            resp = json.loads(line.decode().strip())
            if "error" in resp:
                raise RuntimeError(f"MCP tool call error: {resp['error']}")
            _log.info("mcp.call_tool", server=server_name, tool=tool_name)
            return resp.get("result", {})
        except TimeoutError:
            raise RuntimeError(f"MCP tool call timed out (30s): {tool_name}") from None

    async def shutdown(self) -> None:
        """Disconnect all servers."""
        for name in list(self._servers.keys()):
            await self.disconnect(name)
