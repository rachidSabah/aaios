"""Tests for the Claude Code CodingAgent — protocol, sandbox, manifest, agent lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents import ClaudeCodeCodingAgent
from agents._impls.claude_code import (
    FilesystemSandbox,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    SandboxViolationError,
    build_manifest,
)
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
class TestJSONRPCProtocol:
    """JSON-RPC protocol tests."""

    def test_request_to_line(self) -> None:
        req = JSONRPCRequest(method="test", params={"key": "value"})
        line = req.to_line()
        data = json.loads(line.strip())
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "test"
        assert data["params"] == {"key": "value"}
        assert "id" in data

    def test_request_from_line(self) -> None:
        line = '{"jsonrpc": "2.0", "id": "abc", "method": "test", "params": {}}'
        req = JSONRPCRequest.from_line(line)
        assert req.method == "test"
        assert req.id == "abc"

    def test_response_success(self) -> None:
        resp = JSONRPCResponse.success("abc", {"result": "ok"})
        assert resp.is_error is False
        assert resp.result == {"result": "ok"}

    def test_response_error(self) -> None:
        resp = JSONRPCResponse.error_response("abc", -32601, "Method not found")
        assert resp.is_error is True
        assert resp.error is not None
        assert resp.error["code"] == -32601

    def test_response_to_line_excludes_none(self) -> None:
        resp = JSONRPCResponse.success("abc", "ok")
        line = resp.to_line()
        data = json.loads(line.strip())
        assert "error" not in data

    def test_jsonrpc_error(self) -> None:
        err = JSONRPCError(code=-32000, message="Task failed")
        assert err.code == -32000
        assert "Task failed" in str(err)


@pytest.mark.offline
class TestCapabilityManifest:
    """Capability manifest tests."""

    def test_manifest_has_coding_capabilities(self) -> None:
        manifest = build_manifest()
        caps = manifest.capability_namespaces()
        assert "code.read" in caps
        assert "code.write" in caps
        assert "code.refactor" in caps
        assert "code.review" in caps
        assert "test.run" in caps
        assert "git.commit" in caps
        assert "git.push" in caps
        assert "git.branch" in caps
        assert "shell.execute" in caps

    def test_manifest_identity(self) -> None:
        manifest = build_manifest()
        assert manifest.identity.agent_type == AgentType.CODING
        assert manifest.identity.version == "1.0.0"

    def test_manifest_has_permissions(self) -> None:
        manifest = build_manifest()
        assert len(manifest.permissions_required) >= 3
        perm_names = [p.name for p in manifest.permissions_required]
        assert "gateway.fs.read" in perm_names
        assert "gateway.fs.write" in perm_names
        assert "gateway.shell.exec" in perm_names

    def test_manifest_has_resource_requirements(self) -> None:
        manifest = build_manifest()
        assert manifest.resource_requirements.cpu_cores > 0
        assert manifest.resource_requirements.memory_mb > 0

    def test_manifest_has_cost_model(self) -> None:
        manifest = build_manifest()
        assert manifest.cost_model is not None
        assert manifest.cost_model.per_token_usd > 0

    def test_manifest_has_health_check(self) -> None:
        manifest = build_manifest()
        assert manifest.health_check.interval_s > 0
        assert manifest.health_check.unhealthy_threshold >= 1

    def test_manifest_has_timeout_defaults(self) -> None:
        manifest = build_manifest()
        assert manifest.timeout_defaults.execute_task_s > 0
        assert manifest.timeout_defaults.cancel_task_s > 0


@pytest.mark.offline
class TestFilesystemSandbox:
    """FilesystemSandbox tests."""

    def test_is_safe_within_root(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path)
        assert sandbox.is_safe(tmp_path / "file.txt") is True

    def test_is_safe_outside_root(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path / "project")
        sandbox._root.mkdir(parents=True, exist_ok=True)  # noqa: SLF001
        assert sandbox.is_safe(tmp_path / "outside.txt") is False

    def test_validate_safe_path(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path)
        path = sandbox.validate(tmp_path / "file.txt")
        assert path is not None

    def test_validate_unsafe_raises(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path / "project")
        sandbox._root.mkdir(parents=True, exist_ok=True)  # noqa: SLF001
        with pytest.raises(SandboxViolationError):
            sandbox.validate(tmp_path / "outside.txt")

    def test_resolve_relative_path(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path)
        resolved = sandbox.resolve("src/main.py")
        assert resolved == (tmp_path / "src/main.py").resolve()

    def test_resolve_absolute_path_within_sandbox(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path)
        resolved = sandbox.resolve(str(tmp_path / "src/main.py"))
        assert resolved == (tmp_path / "src/main.py").resolve()

    def test_to_dict(self, tmp_path: Path) -> None:
        sandbox = FilesystemSandbox(tmp_path)
        d = sandbox.to_dict()
        assert "root" in d


@pytest.mark.offline
class TestClaudeCodeCodingAgent:
    """ClaudeCodeCodingAgent tests (mock mode — no real CLI needed)."""

    async def test_initialize_mock_mode(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        assert agent._initialized is True  # noqa: SLF001

    async def test_discover_capabilities(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        manifest = await agent.discover_capabilities()
        assert manifest.identity.agent_id == "claude-code-v1"
        assert manifest.identity.agent_type == AgentType.CODING
        assert "code.read" in manifest.capability_namespaces()

    async def test_execute_task_mock_mode(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="read auth.py",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        result = await agent.execute_task(request)
        assert result.status == TaskResultStatus.SUCCESS
        assert result.output is not None

    async def test_report_health_mock_mode(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        health = await agent.report_health()
        assert health.state == HealthState.HEALTHY

    async def test_shutdown(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        await agent.shutdown()
        assert agent._initialized is False  # noqa: SLF001

    async def test_coding_agent_methods(self, context: AgentContext) -> None:
        """Test CodingAgent Protocol methods (read_file, write_file, etc.)."""
        agent = ClaudeCodeCodingAgent(project_root="/tmp", mock_mode=True)
        await agent.initialize(context)

        # read_file
        content = await agent.read_file(Path("test.py"))
        assert isinstance(content, str)

        # write_file (should not raise)
        await agent.write_file(Path("test.py"), 'print("hello")')

        # run_tests
        result = await agent.run_tests()
        assert isinstance(result, dict)

        # git
        result = await agent.git("status")
        assert isinstance(result, dict)

        # shell
        result = await agent.shell("echo hello")
        assert isinstance(result, dict)

        # review
        result = await agent.review("diff --git a/file b/file")
        assert isinstance(result, dict)

        await agent.shutdown()

    async def test_initialize_is_idempotent(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        await agent.initialize(context)  # should not raise
        assert agent._initialized is True  # noqa: SLF001

    async def test_cancel_task(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        # cancel_task should be idempotent and not raise
        await agent.cancel_task("test-task-id", "test reason")

    async def test_sandbox_integration(self, context: AgentContext, tmp_path: Path) -> None:
        """The agent uses a sandbox when project_root is set."""
        agent = ClaudeCodeCodingAgent(project_root=tmp_path, mock_mode=True)
        await agent.initialize(context)
        # read_file should resolve within the sandbox
        content = await agent.read_file(Path("test.py"))
        assert isinstance(content, str)
        await agent.shutdown()

    async def test_stream_progress(self, context: AgentContext) -> None:
        """stream_progress yields at least one event."""
        from core.contracts.task import TaskProgressKind

        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="test",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        events = []
        async for event in agent.stream_progress(request):
            events.append(event)
        assert len(events) >= 1
        # The last event should be a RESULT
        assert events[-1].kind == TaskProgressKind.RESULT
        await agent.shutdown()

    async def test_serialize_state(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        state = await agent.serialize_state()
        assert state.agent_id == "claude-code-v1"
        await agent.shutdown()

    async def test_restore_state(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        from core.contracts.agent import AgentState

        state = AgentState(agent_id="claude-code-v1", format="1", data={})
        # Should not raise
        await agent.restore_state(state)
        await agent.shutdown()

    async def test_report_metrics(self, context: AgentContext) -> None:
        agent = ClaudeCodeCodingAgent(mock_mode=True)
        await agent.initialize(context)
        request = TaskRequest(
            goal="test",
            context=TaskContext(submitted_by=ActorRef.user("alice")),
        )
        await agent.execute_task(request)
        metrics = await agent.report_metrics()
        assert metrics.agent_id == "claude-code-v1"
        assert metrics.tasks_completed >= 1
        await agent.shutdown()
