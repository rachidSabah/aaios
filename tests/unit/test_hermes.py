"""Tests for the Hermes DesktopAgent — manifest, agent lifecycle, DesktopAgent methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents import HermesDesktopAgent
from agents._impls.hermes import build_manifest
from core.contracts.actor import ActorRef
from core.contracts.agent import AgentContext, AgentEnvironment, AgentType
from core.contracts.health import HealthState
from core.contracts.task import TaskContext, TaskRequest, TaskResultStatus


@pytest.fixture
def context() -> AgentContext:
    """Minimal AgentContext for tests."""
    env = AgentEnvironment(
        home_dir=Path("/tmp"),
        config_dir=Path("/tmp/aaios/config"),
        data_dir=Path("/tmp/aaios/data"),
        log_dir=Path("/tmp/aaios/logs"),
        temp_dir=Path("/tmp/aaios/temp"),
    )
    return AgentContext(environment=env)


@pytest.mark.offline
class TestHermesCapabilityManifest:
    """Hermes capability manifest tests."""

    def test_manifest_has_desktop_capabilities(self) -> None:
        manifest = build_manifest()
        caps = manifest.capability_namespaces()
        assert "desktop.ui.click" in caps
        assert "desktop.ui.find_element" in caps
        assert "desktop.input.type_text" in caps
        assert "desktop.screen.screenshot" in caps
        assert "desktop.screen.ocr" in caps
        assert "desktop.app.open" in caps
        assert "desktop.app.close" in caps
        assert "desktop.file.manage" in caps

    def test_manifest_has_browser_capabilities(self) -> None:
        manifest = build_manifest()
        caps = manifest.capability_namespaces()
        assert "browser.navigate" in caps
        assert "browser.click" in caps
        assert "browser.input" in caps
        assert "browser.extract" in caps
        assert "browser.screenshot" in caps

    def test_manifest_identity(self) -> None:
        manifest = build_manifest()
        assert manifest.identity.agent_type == AgentType.DESKTOP
        assert manifest.identity.version == "1.0.0"

    def test_manifest_has_14_capabilities(self) -> None:
        manifest = build_manifest()
        assert len(manifest.capability_namespaces()) == 14

    def test_manifest_permissions(self) -> None:
        manifest = build_manifest()
        perm_names = [p.name for p in manifest.permissions_required]
        assert "gateway.desktop.input" in perm_names
        assert "gateway.process.spawn" in perm_names
        assert "gateway.fs.write" in perm_names
        assert "gateway.net.request" in perm_names

    def test_manifest_resource_requirements(self) -> None:
        manifest = build_manifest()
        assert manifest.resource_requirements.memory_mb >= 512  # higher than coding agent

    def test_manifest_cost_model(self) -> None:
        manifest = build_manifest()
        assert manifest.cost_model is not None
        assert manifest.cost_model.fixed_usd == 0.0  # local execution


@pytest.mark.offline
class TestHermesDesktopAgent:
    """HermesDesktopAgent tests (mock mode)."""

    async def test_initialize_mock_mode(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        assert agent._initialized is True  # noqa: SLF001

    async def test_discover_capabilities(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        manifest = await agent.discover_capabilities()
        assert manifest.identity.agent_id == "hermes-desktop-v1"
        assert manifest.identity.agent_type == AgentType.DESKTOP
        assert len(manifest.capability_namespaces()) == 14

    async def test_execute_task(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="open notepad and type hello",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.SUCCESS

    async def test_report_health(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        health = await agent.report_health()
        assert health.state == HealthState.HEALTHY

    async def test_shutdown(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        await agent.shutdown()
        assert agent._initialized is False  # noqa: SLF001

    async def test_initialize_idempotent(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        await agent.initialize(context)
        assert agent._initialized is True  # noqa: SLF001

    async def test_desktop_agent_methods(self, context: AgentContext) -> None:
        """Test DesktopAgent Protocol methods."""
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)

        # open_app
        result = await agent.open_app("notepad")
        assert isinstance(result, dict)
        assert "pid" in result

        # close_app (should not raise)
        await agent.close_app(12345)

        # click (should not raise)
        await agent.click(100, 200)

        # type_text (should not raise)
        await agent.type_text("hello world")

        # screenshot
        screenshot = await agent.screenshot()
        assert isinstance(screenshot, bytes)
        assert len(screenshot) > 0

        # ocr
        text = await agent.ocr()
        assert isinstance(text, str)
        assert len(text) > 0

        # find_element
        elem = await agent.find_element("OK button")
        assert isinstance(elem, dict)
        assert elem.get("found") is True

        # manage_file (should not raise)
        result = await agent.manage_file("copy", Path("/tmp/a.txt"), Path("/tmp/b.txt"))
        assert isinstance(result, dict)

        await agent.shutdown()

    async def test_browser_methods(self, context: AgentContext) -> None:
        """Test browser.* capability methods."""
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)

        # browser_navigate
        result = await agent.browser_navigate("https://example.com")
        assert isinstance(result, dict)

        # browser_click (should not raise)
        await agent.browser_click("#submit-button")

        # browser_input (should not raise)
        await agent.browser_input("#search-box", "hello")

        # browser_extract
        result = await agent.browser_extract(".result-item")
        assert isinstance(result, dict)

        # browser_screenshot
        screenshot = await agent.browser_screenshot()
        assert isinstance(screenshot, bytes)

        await agent.shutdown()

    async def test_ocr_with_region(self, context: AgentContext) -> None:
        """OCR with a specific region."""
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        text = await agent.ocr(region=(0, 0, 100, 100))
        assert isinstance(text, str)
        await agent.shutdown()

    async def test_cancel_task(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        await agent.cancel_task("test-task", "test reason")

    async def test_stream_progress(self, context: AgentContext) -> None:
        from core.contracts.task import TaskProgressKind

        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="test",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        events = []
        async for event in agent.stream_progress(request):
            events.append(event)
        assert len(events) >= 1
        assert events[-1].kind == TaskProgressKind.RESULT
        await agent.shutdown()

    async def test_serialize_state(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        state = await agent.serialize_state()
        assert state.agent_id == "hermes-desktop-v1"
        await agent.shutdown()

    async def test_report_metrics(self, context: AgentContext) -> None:
        agent = HermesDesktopAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="test",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        await agent.execute_task(request)
        metrics = await agent.report_metrics()
        assert metrics.agent_id == "hermes-desktop-v1"
        assert metrics.tasks_completed >= 1
        await agent.shutdown()
