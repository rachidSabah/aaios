"""Tests for Phase 11 — Plugin Manager, MCP Manager, Plugin SDK, Agent SDK."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.agent_sdk import scaffold_agent
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
    """MCPManager tests."""

    async def test_register(self) -> None:
        mgr = MCPManager()
        config = MCPServerConfig(name="test", command="echo test")
        name = await mgr.register(config)
        assert name == "test"
        assert mgr.get_server("test") is not None

    async def test_connect(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo test"))
        assert await mgr.connect("test") is True
        server = mgr.get_server("test")
        assert server.tools == ["mock_tool_1", "mock_tool_2"]

    async def test_disconnect(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        await mgr.connect("test")
        assert await mgr.disconnect("test") is True
        assert mgr.get_server("test").tools == []

    async def test_reload(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        await mgr.connect("test")
        assert await mgr.reload("test") is True

    async def test_unregister(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        assert await mgr.unregister("test") is True
        assert mgr.get_server("test") is None

    async def test_list_tools(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        await mgr.connect("test")
        tools = mgr.list_tools("test")
        assert len(tools) == 2

    async def test_list_all_tools(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="s1", command="echo"))
        await mgr.register(MCPServerConfig(name="s2", command="echo"))
        await mgr.connect("s1")
        await mgr.connect("s2")
        all_tools = mgr.list_all_tools()
        assert "s1" in all_tools
        assert "s2" in all_tools

    async def test_call_tool(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        await mgr.connect("test")
        result = await mgr.call_tool("test", "mock_tool_1", {"arg": "value"})
        assert result["mock"] is True
        assert result["tool"] == "mock_tool_1"

    async def test_call_tool_not_connected(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        with pytest.raises(RuntimeError, match="not connected"):
            await mgr.call_tool("test", "tool", {})

    async def test_call_unknown_tool(self) -> None:
        mgr = MCPManager()
        await mgr.register(MCPServerConfig(name="test", command="echo"))
        await mgr.connect("test")
        with pytest.raises(ValueError, match="not found"):
            await mgr.call_tool("test", "nonexistent", {})

    async def test_discover(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mcp-servers"
        config_dir.mkdir()
        (config_dir / "slack.json").write_text(
            json.dumps(
                {
                    "name": "slack",
                    "command": "npx @mcp/slack",
                }
            )
        )

        mgr = MCPManager(config_dir=config_dir)
        discovered = await mgr.discover()
        assert "slack" in discovered


@pytest.mark.offline
class TestAgentSDK:
    """Agent SDK scaffold tests."""

    def test_scaffold_in_process(self, tmp_path: Path) -> None:
        path = scaffold_agent(
            name="my-agent",
            agent_type="research",
            style="in_process",
            output_dir=tmp_path,
        )
        assert path.is_dir()
        assert (path / "plugin.json").is_file()
        assert (path / "__init__.py").is_file()
        assert (path / "agent" / "agent.py").is_file()
        assert (path / "README.md").is_file()

        # Verify the manifest
        manifest = json.loads((path / "plugin.json").read_text())
        assert manifest["name"] == "my-agent"
        assert manifest["version"] == "0.1.0"

    def test_scaffold_subprocess(self, tmp_path: Path) -> None:
        path = scaffold_agent(
            name="sub-agent",
            agent_type="coding",
            style="subprocess",
            output_dir=tmp_path,
        )
        agent_code = (path / "agent" / "agent.py").read_text()
        assert "SubprocessBridgeAgent" in agent_code

    def test_scaffold_remote(self, tmp_path: Path) -> None:
        path = scaffold_agent(
            name="remote-agent",
            agent_type="browser",
            style="remote",
            output_dir=tmp_path,
        )
        agent_code = (path / "agent" / "agent.py").read_text()
        assert "RemoteServiceAgent" in agent_code


@pytest.mark.offline
class TestExamplePlugins:
    """Verify the example plugin manifests are valid."""

    def test_weather_manifest(self) -> None:
        from plugins.examples.weather.weather_plugin import manifest

        assert manifest.name == "weather"
        assert manifest.version == "1.0.0"
        assert len(manifest.provides_tools) == 1

    def test_calculator_manifest(self) -> None:
        from plugins.examples.calculator.calculator_plugin import manifest

        assert manifest.name == "calculator"
        assert manifest.version == "1.0.0"

    def test_calculator_safe_eval(self) -> None:
        from plugins.examples.calculator.calculator_plugin import _safe_eval

        assert _safe_eval("2 + 3") == 5.0
        assert _safe_eval("2 * 3") == 6.0
        assert _safe_eval("10 / 2") == 5.0
        assert _safe_eval("2 ** 3") == 8.0

    def test_calculator_safe_eval_rejects_imports(self) -> None:
        from plugins.examples.calculator.calculator_plugin import _safe_eval

        with pytest.raises(ValueError):
            _safe_eval('__import__("os")')

    def test_openhands_manifest(self) -> None:
        """The OpenHands scaffold manifest is valid JSON."""
        manifest_path = (
            Path(__file__).resolve().parents[2]
            / "plugins"
            / "examples"
            / "openhands_agent"
            / "plugin.json"
        )
        data = json.loads(manifest_path.read_text())
        assert data["name"] == "openhands-agent"
        assert "code.read" not in data  # capabilities are in the agent code, not manifest
