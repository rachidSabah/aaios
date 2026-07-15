"""Tests for Phase 11 — Plugin Manager, MCP Manager, Plugin SDK, Agent SDK."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.mcp import MCPManager, MCPServerConfig
from services.plugin import PluginManager, PluginManifest, PluginState
from services.plugin.sdk import PluginManifestBuilder


@pytest.mark.offline
class TestPluginManifest:
    """PluginManifest tests."""

    def test_basic_manifest(self) -> None:
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            entry_point="test_plugin",
        )
        assert manifest.name == "test"
        assert manifest.version == "1.0.0"
        assert manifest.provides_agents == []
        assert manifest.provides_tools == []

    def test_manifest_with_provides(self) -> None:
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            provides_agents=["test.agent.MyAgent"],
            provides_tools=["test.register_tools"],
            entry_point="test",
        )
        assert len(manifest.provides_agents) == 1
        assert len(manifest.provides_tools) == 1


@pytest.mark.offline
class TestPluginManifestBuilder:
    """PluginManifestBuilder tests."""

    def test_build_basic(self) -> None:
        manifest = PluginManifestBuilder("weather", "1.0.0").description("Weather plugin").build()
        assert manifest.name == "weather"
        assert manifest.version == "1.0.0"
        assert manifest.description == "Weather plugin"

    def test_build_with_provides(self) -> None:
        manifest = (
            PluginManifestBuilder("test", "1.0.0")
            .provides_agents("test.Agent")
            .provides_tools("test.register")
            .provides_providers("test.Provider")
            .build()
        )
        assert manifest.provides_agents == ["test.Agent"]
        assert manifest.provides_tools == ["test.register"]
        assert manifest.provides_providers == ["test.Provider"]

    def test_build_with_requirements(self) -> None:
        manifest = (
            PluginManifestBuilder("test", "1.0.0")
            .requires_permissions("gateway.net.request")
            .requires_api_keys("test/api_key")
            .build()
        )
        assert "gateway.net.request" in manifest.requires_permissions
        assert "test/api_key" in manifest.requires_api_keys

    def test_build_with_entry_point(self) -> None:
        manifest = PluginManifestBuilder("test", "1.0.0").entry_point("my_module").build()
        assert manifest.entry_point == "my_module"

    def test_build_defaults_entry_point_to_name(self) -> None:
        manifest = PluginManifestBuilder("test", "1.0.0").build()
        assert manifest.entry_point == "test"


@pytest.mark.offline
class TestPluginManager:
    """PluginManager tests."""

    async def test_install_from_manifest(self) -> None:
        mgr = PluginManager()
        manifest = PluginManifest(name="test", version="1.0.0", entry_point="test")
        name = await mgr.install_from_manifest(manifest)
        assert name == "test"
        assert mgr.get_plugin("test") is not None
        assert mgr.get_plugin("test").state == PluginState.INSTALLED

    async def test_list_plugins(self) -> None:
        mgr = PluginManager()
        await mgr.install_from_manifest(PluginManifest(name="a", version="1.0.0", entry_point="a"))
        await mgr.install_from_manifest(PluginManifest(name="b", version="1.0.0", entry_point="b"))
        plugins = mgr.list_plugins()
        assert len(plugins) == 2

    async def test_disable(self) -> None:
        mgr = PluginManager()
        await mgr.install_from_manifest(
            PluginManifest(name="test", version="1.0.0", entry_point="test")
        )
        assert await mgr.disable("test") is True
        assert mgr.get_plugin("test").state == PluginState.DISABLED

    async def test_disable_unknown(self) -> None:
        mgr = PluginManager()
        assert await mgr.disable("nonexistent") is False

    async def test_uninstall(self) -> None:
        mgr = PluginManager()
        await mgr.install_from_manifest(
            PluginManifest(name="test", version="1.0.0", entry_point="test")
        )
        assert await mgr.uninstall("test") is True
        assert mgr.get_plugin("test") is None

    async def test_uninstall_unknown(self) -> None:
        mgr = PluginManager()
        assert await mgr.uninstall("nonexistent") is False

    async def test_discover(self, tmp_path: Path) -> None:
        """Discovery scans for plugin.json files."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        weather_dir = plugin_dir / "weather"
        weather_dir.mkdir()
        (weather_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "weather",
                    "version": "1.0.0",
                    "entry_point": "weather_plugin",
                }
            )
        )

        mgr = PluginManager(plugin_dir=plugin_dir)
        discovered = await mgr.discover()
        assert "weather" in discovered
        assert mgr.get_plugin("weather") is not None


@pytest.mark.offline
class TestMCPManager:
    """MCPManager tests — uses a real mock MCP server subprocess."""

    import sys

    _MOCK_SERVER = (
        sys.executable
        + " "
        + str(Path(__file__).resolve().parent.parent / "fixtures" / "mock_mcp_server.py")
    )

    async def test_register(self) -> None:
        mgr = MCPManager()
        config = MCPServerConfig(name="test", command="echo", args=["test"])
        name = await mgr.register(config)
        assert name == "test"
        assert mgr.get_server("test") is not None

    async def test_connect_with_mock_server(self) -> None:
        """Connect to a real mock MCP server subprocess."""
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        assert await mgr.connect("test") is True
        server = mgr.get_server("test")
        assert server.tools == ["mock_tool_1", "mock_tool_2"]
        await mgr.disconnect("test")

    async def test_connect_failure(self) -> None:
        """Connecting to a non-MCP command fails gracefully."""
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="bad", command="false"))
        result = await mgr.connect("bad")
        assert result is False or mgr.get_server("bad").state.value == "error"

    async def test_disconnect(self) -> None:
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        await mgr.connect("test")
        assert await mgr.disconnect("test") is True
        assert mgr.get_server("test").tools == []

    async def test_reload(self) -> None:
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        await mgr.connect("test")
        assert await mgr.reload("test") is True
        await mgr.disconnect("test")

    async def test_unregister(self) -> None:
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        await mgr.connect("test")
        assert await mgr.unregister("test") is True
        assert mgr.get_server("test") is None

    async def test_list_tools(self) -> None:
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        await mgr.connect("test")
        tools = mgr.list_tools("test")
        assert len(tools) == 2
        await mgr.disconnect("test")

    async def test_list_all_tools(self) -> None:
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="s1", command=parts[0], args=parts[1:]))
        await mgr.register(MCPServerConfig(name="s2", command=parts[0], args=parts[1:]))
        await mgr.connect("s1")
        await mgr.connect("s2")
        all_tools = mgr.list_all_tools()
        assert "s1" in all_tools
        assert "s2" in all_tools
        await mgr.disconnect("s1")
        await mgr.disconnect("s2")

    async def test_call_tool(self) -> None:
        """Call a tool on the real mock MCP server."""
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        await mgr.connect("test")
        result = await mgr.call_tool("test", "mock_tool_1", {"arg": "value"})
        assert "content" in result
        assert "mock_tool_1" in result["content"][0]["text"]
        await mgr.disconnect("test")

    async def test_call_tool_not_connected(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        with pytest.raises(RuntimeError, match="not connected"):
            await mgr.call_tool("test", "tool", {})

    async def test_call_unknown_tool(self) -> None:
        import shlex

        parts = shlex.split(self._MOCK_SERVER)
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command=parts[0], args=parts[1:]))
        await mgr.connect("test")
        with pytest.raises(ValueError, match="not found"):
            await mgr.call_tool("test", "nonexistent", {})
        await mgr.disconnect("test")

    async def test_discover(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mcp-servers"
        config_dir.mkdir()
        (config_dir / "slack.json").write_text(
            json.dumps(
                {
                    "name": "slack",
                    "command": "npx",
                    "args": ["@mcp/slack"],
                }
            )
        )

        mgr = MCPManager(config_dir=config_dir)
        discovered = await mgr.discover()
        assert "slack" in discovered
