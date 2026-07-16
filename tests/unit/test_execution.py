"""Tests for the Autonomous Execution Platform (v4.0)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from services.execution import (
    ApprovalEngine,
    ApprovalStatus,
    ExecutionDomain,
    ExecutionManager,
    ExecutionNotFoundError,
    ExecutionPolicy,
    ExecutionRequest,
    ExecutionStatus,
    PolicyEngine,
    Sandbox,
    SandboxConfig,
    get_handler,
)


def _make_request(
    *,
    domain: str = ExecutionDomain.TERMINAL.value,
    action: str = "run_command",
    parameters: dict | None = None,
    policy: ExecutionPolicy | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        domain=domain,
        action=action,
        parameters=parameters or {"command": "echo test", "shell": "bash"},
        policy=policy or ExecutionPolicy(sandbox_enabled=False),
    )


# ============================================================
# Models
# ============================================================


@pytest.mark.offline
class TestExecutionModels:
    """Execution model tests."""

    def test_execution_request_creation(self) -> None:
        req = _make_request()
        assert req.domain == ExecutionDomain.TERMINAL.value
        assert req.status == ExecutionStatus.PENDING.value

    def test_policy_domain_check(self) -> None:
        p = ExecutionPolicy(allowed_domains=["filesystem"], denied_domains=["terminal"])
        assert p.is_domain_allowed("filesystem") is True
        assert p.is_domain_allowed("terminal") is False

    def test_policy_path_check(self) -> None:
        p = ExecutionPolicy(denied_paths=["/etc", "/root"])
        assert p.is_path_allowed("/tmp/test") is True
        assert p.is_path_allowed("/etc/passwd") is False

    def test_policy_host_check(self) -> None:
        p = ExecutionPolicy(allowed_hosts=["localhost"])
        assert p.is_host_allowed("localhost") is True
        assert p.is_host_allowed("evil.com") is False

    def test_result_to_dict(self) -> None:
        req = _make_request()
        from services.execution import ExecutionResult
        r = ExecutionResult(execution_id=req.execution_id, status="succeeded", exit_code=0)
        d = r.to_dict()
        assert d["status"] == "succeeded"
        assert d["succeeded"] is True


# ============================================================
# Policy Engine
# ============================================================


@pytest.mark.offline
class TestPolicyEngine:
    """PolicyEngine tests."""

    async def test_evaluate_allowed(self) -> None:
        engine = PolicyEngine()
        req = _make_request()
        decision = await engine.evaluate(req)
        assert decision.allowed is True

    async def test_evaluate_denied_domain(self) -> None:
        engine = PolicyEngine()
        req = _make_request(policy=ExecutionPolicy(denied_domains=[ExecutionDomain.TERMINAL.value]))
        decision = await engine.evaluate(req)
        assert decision.allowed is False

    async def test_high_risk_requires_approval(self) -> None:
        engine = PolicyEngine()
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="delete_file",
            parameters={"path": "/tmp/test"},
        )
        decision = await engine.evaluate(req)
        assert decision.requires_approval is True
        assert decision.risk_level in ("high", "critical")

    async def test_rate_limit(self) -> None:
        engine = PolicyEngine()
        req = _make_request(policy=ExecutionPolicy(rate_limit_per_minute=2))
        d1 = await engine.evaluate(req)
        d2 = await engine.evaluate(req)
        d3 = await engine.evaluate(req)
        assert d1.allowed is True
        assert d2.allowed is True
        assert d3.allowed is False  # rate limited


# ============================================================
# Approval Engine
# ============================================================


@pytest.mark.offline
class TestApprovalEngine:
    """ApprovalEngine tests."""

    async def test_request_and_approve(self) -> None:
        engine = ApprovalEngine()
        approval = await engine.request_approval("exec-1", "filesystem", "delete_file", "Delete a file")
        assert approval.status == ApprovalStatus.PENDING.value
        result = await engine.approve(approval.approval_id, "operator", "OK")
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED.value

    async def test_reject(self) -> None:
        engine = ApprovalEngine()
        approval = await engine.request_approval("exec-2", "terminal", "run_command", "Run command")
        result = await engine.reject(approval.approval_id, "operator", "No")
        assert result is not None
        assert result.status == ApprovalStatus.REJECTED.value

    async def test_get_pending(self) -> None:
        engine = ApprovalEngine()
        await engine.request_approval("exec-3", "git", "push", "Push to main")
        pending = await engine.get_pending()
        assert len(pending) >= 1

    async def test_approve_nonexistent(self) -> None:
        engine = ApprovalEngine()
        result = await engine.approve("nonexistent", "operator", "")
        assert result is None


# ============================================================
# Sandbox
# ============================================================


@pytest.mark.offline
class TestSandbox:
    """Sandbox tests."""

    async def test_setup_and_cleanup(self, tmp_path: Path) -> None:
        config = SandboxConfig(
            enabled=True,
            working_dir=str(tmp_path / "work"),
            temp_dir=str(tmp_path / "tmp"),
            log_dir=str(tmp_path / "logs"),
        )
        sandbox = Sandbox(config)
        await sandbox.setup()
        assert sandbox.is_active is True
        assert Path(config.working_dir).exists()
        await sandbox.cleanup()
        assert sandbox.is_active is False

    async def test_create_temp_file(self, tmp_path: Path) -> None:
        config = SandboxConfig(
            enabled=True,
            working_dir=str(tmp_path / "work"),
            temp_dir=str(tmp_path / "tmp"),
            log_dir=str(tmp_path / "logs"),
        )
        sandbox = Sandbox(config)
        await sandbox.setup()
        f = sandbox.create_temp_file(suffix=".txt")
        assert f.exists()
        await sandbox.cleanup()


# ============================================================
# Domain Handlers
# ============================================================


@pytest.mark.offline
class TestFileSystemHandler:
    """FileSystemHandler tests."""

    async def test_write_and_read(self, tmp_path: Path) -> None:
        handler = get_handler(ExecutionDomain.FILESYSTEM.value)
        assert handler is not None
        file_path = tmp_path / "test.txt"
        write_req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="write_file",
            parameters={"path": str(file_path), "content": "hello"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(write_req)
        assert result.succeeded is True
        assert file_path.read_text() == "hello"

        read_req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="read_file",
            parameters={"path": str(file_path)},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result2 = await handler.execute(read_req)
        assert result2.succeeded is True
        assert result2.output == "hello"

    async def test_delete_with_rollback(self, tmp_path: Path) -> None:
        handler = get_handler(ExecutionDomain.FILESYSTEM.value)
        file_path = tmp_path / "delete_me.txt"
        file_path.write_text("original content")
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="delete_file",
            parameters={"path": str(file_path)},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is True
        assert not file_path.exists()
        assert result.rollback_plan is not None
        assert result.rollback_plan.can_rollback is True

    async def test_list_directory(self, tmp_path: Path) -> None:
        handler = get_handler(ExecutionDomain.FILESYSTEM.value)
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="list_directory",
            parameters={"path": str(tmp_path)},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is True
        names = [e["name"] for e in result.output]
        assert "a.txt" in names
        assert "b.txt" in names

    async def test_checksum(self, tmp_path: Path) -> None:
        handler = get_handler(ExecutionDomain.FILESYSTEM.value)
        file_path = tmp_path / "hash.txt"
        file_path.write_text("test content")
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="checksum",
            parameters={"path": str(file_path)},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is True
        assert "sha256" in result.output

    async def test_unknown_action(self) -> None:
        handler = get_handler(ExecutionDomain.FILESYSTEM.value)
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="nonexistent_action",
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is False
        assert "Unknown" in (result.error or "")


@pytest.mark.offline
class TestTerminalHandler:
    """TerminalHandler tests."""

    async def test_run_command(self) -> None:
        handler = get_handler(ExecutionDomain.TERMINAL.value)
        assert handler is not None
        req = _make_request(
            parameters={"command": "echo hello_world", "shell": "bash"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is True
        assert "hello_world" in result.stdout

    async def test_command_failure(self) -> None:
        handler = get_handler(ExecutionDomain.TERMINAL.value)
        req = _make_request(
            parameters={"command": "exit 1", "shell": "bash"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.status == ExecutionStatus.FAILED.value
        assert result.exit_code == 1

    async def test_command_timeout(self) -> None:
        handler = get_handler(ExecutionDomain.TERMINAL.value)
        req = _make_request(
            parameters={"command": "sleep 10", "shell": "bash", "timeout_s": 0.5},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        req.timeout_s = 0.5
        result = await handler.execute(req)
        assert result.status == ExecutionStatus.TIMEOUT.value

    async def test_no_command(self) -> None:
        handler = get_handler(ExecutionDomain.TERMINAL.value)
        req = _make_request(
            parameters={"shell": "bash"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is False


@pytest.mark.offline
class TestDatabaseHandler:
    """DatabaseHandler tests."""

    async def test_sqlite_query(self, tmp_path: Path) -> None:
        import sqlite3
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        conn.close()
        handler = get_handler(ExecutionDomain.DATABASE.value)
        req = _make_request(
            domain=ExecutionDomain.DATABASE.value,
            action="query",
            parameters={"type": "sqlite", "path": str(db_path), "sql": "SELECT * FROM test"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is True
        assert result.output[0]["name"] == "hello"


@pytest.mark.offline
class TestRestApiHandler:
    """RestApiHandler tests."""

    async def test_get_request(self) -> None:
        handler = get_handler(ExecutionDomain.REST_API.value)
        req = _make_request(
            domain=ExecutionDomain.REST_API.value,
            action="get",
            parameters={"url": "https://httpbin.org/get"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        req.timeout_s = 15.0
        result = await handler.execute(req)
        # May fail if no network, but should not crash
        assert result.status in (ExecutionStatus.SUCCEEDED.value, ExecutionStatus.FAILED.value)

    async def test_no_url(self) -> None:
        handler = get_handler(ExecutionDomain.REST_API.value)
        req = _make_request(
            domain=ExecutionDomain.REST_API.value,
            action="get",
            parameters={},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await handler.execute(req)
        assert result.succeeded is False


@pytest.mark.offline
class TestStubHandlers:
    """Test that stub handlers return clear errors."""

    async def test_browser_handler_graceful_degradation(self) -> None:
        handler = get_handler(ExecutionDomain.BROWSER.value)
        req = _make_request(domain=ExecutionDomain.BROWSER.value, policy=ExecutionPolicy(sandbox_enabled=False))
        result = await handler.execute(req)
        # Should either fail with playwright install message (if not installed)
        # or fail with unknown action (if playwright IS installed)
        assert result.succeeded is False

    async def test_cloud_handler_graceful_degradation(self) -> None:
        handler = get_handler(ExecutionDomain.CLOUD.value)
        req = _make_request(domain=ExecutionDomain.CLOUD.value, policy=ExecutionPolicy(sandbox_enabled=False))
        result = await handler.execute(req)
        assert result.succeeded is False

    async def test_email_handler_graceful_degradation(self) -> None:
        handler = get_handler(ExecutionDomain.EMAIL.value)
        req = _make_request(domain=ExecutionDomain.EMAIL.value, policy=ExecutionPolicy(sandbox_enabled=False))
        result = await handler.execute(req)
        assert result.succeeded is False

    async def test_all_domains_have_handlers(self) -> None:
        for domain in ExecutionDomain:
            handler = get_handler(domain.value)
            assert handler is not None, f"No handler for domain {domain}"


# ============================================================
# ExecutionManager (Integration)
# ============================================================


@pytest.mark.offline
class TestExecutionManager:
    """ExecutionManager integration tests."""

    async def test_execute_terminal(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(
            parameters={"command": "echo integration_test", "shell": "bash"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await mgr.execute(req)
        assert result.succeeded is True
        assert "integration_test" in result.stdout

    async def test_execute_filesystem(self, tmp_path: Path) -> None:
        mgr = ExecutionManager()
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="write_file",
            parameters={"path": str(tmp_path / "mgr_test.txt"), "content": "mgr"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await mgr.execute(req)
        assert result.succeeded is True

    async def test_get_status(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(policy=ExecutionPolicy(sandbox_enabled=False))
        await mgr.execute(req)
        status = await mgr.get_status(req.execution_id)
        assert status.execution_id == req.execution_id

    async def test_get_status_not_found(self) -> None:
        mgr = ExecutionManager()
        with pytest.raises(ExecutionNotFoundError):
            await mgr.get_status("nonexistent")

    async def test_cancel(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(policy=ExecutionPolicy(sandbox_enabled=False))
        await mgr.execute(req)
        result = await mgr.cancel(req.execution_id, reason="test")
        assert result.status in (ExecutionStatus.CANCELLED.value, ExecutionStatus.SUCCEEDED.value)

    async def test_history(self) -> None:
        mgr = ExecutionManager()
        for _ in range(3):
            req = _make_request(policy=ExecutionPolicy(sandbox_enabled=False))
            await mgr.execute(req)
        history = await mgr.get_history()
        assert len(history) >= 3

    async def test_audit_log(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(policy=ExecutionPolicy(sandbox_enabled=False))
        await mgr.execute(req)
        audit = await mgr.get_audit_log()
        assert len(audit) >= 3  # policy_check + dispatched + completed

    async def test_replay(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(
            parameters={"command": "echo replay_test", "shell": "bash"},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        await mgr.execute(req)
        replayed = await mgr.replay(req.execution_id)
        assert replayed.succeeded is True

    async def test_rollback(self, tmp_path: Path) -> None:
        mgr = ExecutionManager()
        file_path = tmp_path / "rollback_test.txt"
        file_path.write_text("original")
        req = _make_request(
            domain=ExecutionDomain.FILESYSTEM.value,
            action="delete_file",
            parameters={"path": str(file_path)},
            policy=ExecutionPolicy(sandbox_enabled=False),
        )
        result = await mgr.execute(req)
        assert result.succeeded is True
        assert not file_path.exists()
        # Rollback
        rb = await mgr.rollback(req.execution_id)
        assert rb.succeeded is True
        assert file_path.exists()
        assert file_path.read_text() == "original"

    async def test_policy_rejection(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(
            policy=ExecutionPolicy(
                denied_domains=[ExecutionDomain.TERMINAL.value],
                sandbox_enabled=False,
            ),
        )
        result = await mgr.execute(req)
        assert result.status == ExecutionStatus.REJECTED.value

    async def test_logs(self) -> None:
        mgr = ExecutionManager()
        req = _make_request(policy=ExecutionPolicy(sandbox_enabled=False))
        await mgr.execute(req)
        logs = await mgr.get_logs(req.execution_id)
        assert len(logs) > 0


# ============================================================
# Stress Tests
# ============================================================


@pytest.mark.offline
class TestExecutionStress:
    """Stress tests for the execution platform."""

    async def test_concurrent_executions(self) -> None:
        mgr = ExecutionManager()

        async def execute_one(i: int):
            req = _make_request(
                parameters={"command": f"echo task_{i}", "shell": "bash"},
                policy=ExecutionPolicy(sandbox_enabled=False),
            )
            return await mgr.execute(req)

        results = await asyncio.gather(*[execute_one(i) for i in range(20)])
        assert all(r.succeeded for r in results)
        assert len(results) == 20

    async def test_many_filesystem_ops(self, tmp_path: Path) -> None:
        mgr = ExecutionManager()
        for i in range(50):
            req = _make_request(
                domain=ExecutionDomain.FILESYSTEM.value,
                action="write_file",
                parameters={"path": str(tmp_path / f"file_{i}.txt"), "content": f"content_{i}"},
                policy=ExecutionPolicy(sandbox_enabled=False),
            )
            result = await mgr.execute(req)
            assert result.succeeded is True
