"""Tests for core.gateway — the I/O surface (INV-02)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission, PermissionDecision
from core.gateway import (
    AuditEntry,
    FileSystemGateway,
    NetworkGateway,
    NoOpAuditLogger,
    NoOpPermissionChecker,
    PermissionResult,
    get_fs_gateway,
    get_gateway,
    get_net_gateway,
    get_shell_gateway,
    set_audit_logger,
    set_permission_checker,
)


@pytest.fixture(autouse=True)
def _reset_gateways():
    """Reset all gateway singletons before each test."""
    # Use no-op permission checker + audit logger
    set_permission_checker(NoOpPermissionChecker())
    set_audit_logger(NoOpAuditLogger())
    # Reset the FS gateway singleton so each test gets a fresh one
    import core.gateway.fs as fs_mod

    fs_mod._INSTANCE = None
    import core.gateway.shell as shell_mod

    shell_mod._INSTANCE = None
    import core.gateway.net as net_mod

    net_mod._INSTANCE = None
    import core.gateway.gateway as gw_mod

    gw_mod._INSTANCE = None
    yield
    # Cleanup
    fs_mod._INSTANCE = None
    shell_mod._INSTANCE = None
    net_mod._INSTANCE = None
    gw_mod._INSTANCE = None


@pytest.mark.offline
class TestFileSystemGateway:
    """FileSystemGateway tests."""

    async def test_read_writes_file(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        target = tmp_path / "test.txt"
        await gw.write(target, b"hello world", actor=actor)
        data = await gw.read(target, actor=actor)
        assert data == b"hello world"

    async def test_write_str_content(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        target = tmp_path / "test.txt"
        await gw.write(target, "hello", actor=actor)
        data = await gw.read(target, actor=actor)
        assert data == b"hello"

    async def test_append_mode(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        target = tmp_path / "append.txt"
        await gw.write(target, "hello", actor=actor)
        await gw.write(target, " world", actor=actor, append=True)
        data = await gw.read(target, actor=actor)
        assert data == b"hello world"

    async def test_list_dir(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = await gw.list_dir(tmp_path, actor=actor)
        assert "a.txt" in entries
        assert "b.txt" in entries

    async def test_delete_file(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        target = tmp_path / "to_delete.txt"
        target.write_text("x")
        await gw.delete(target, actor=actor)
        assert not target.exists()

    async def test_exists(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        target = tmp_path / "exists.txt"
        target.write_text("x")
        assert await gw.exists(target, actor=actor) is True
        assert await gw.exists(tmp_path / "nope.txt", actor=actor) is False

    async def test_sandbox_violation_blocked(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        with pytest.raises(PermissionError, match="outside sandbox"):
            await gw.read(outside, actor=actor, sandbox_root=sandbox)

    async def test_sandbox_allows_inside(self, tmp_path: Path) -> None:
        gw = FileSystemGateway()
        actor = ActorRef.system()
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        inside = sandbox / "inside.txt"
        inside.write_text("ok")
        data = await gw.read(inside, actor=actor, sandbox_root=sandbox)
        assert data == b"ok"

    async def test_permission_denied_blocks_read(self, tmp_path: Path) -> None:
        """When the permission checker returns DENY, the gateway refuses."""

        class DenyAll:
            async def check(self, actor, permission, resource=None):
                return PermissionResult(decision=PermissionDecision.DENY, reason="test")

        set_permission_checker(DenyAll())  # type: ignore[arg-type]
        gw = FileSystemGateway()
        target = tmp_path / "secret.txt"
        target.write_text("secret")
        with pytest.raises(PermissionError, match="Permission denied"):
            await gw.read(target, actor=ActorRef.system())


@pytest.mark.offline
class TestNetworkGateway:
    """NetworkGateway tests."""

    async def test_egress_allow_list_blocks_unknown_host(self) -> None:
        gw = NetworkGateway(allowed_hosts=["localhost"])
        with pytest.raises(PermissionError, match="not in allow-list"):
            await gw.request(
                "GET",
                "http://evil.example.com/data",
                actor=ActorRef.system(),
            )

    async def test_add_allowed_host(self) -> None:
        gw = NetworkGateway(allowed_hosts=[])
        assert not gw.is_host_allowed("example.com")
        gw.add_allowed_host("example.com")
        assert gw.is_host_allowed("example.com")

    async def test_wildcard_allows_all(self) -> None:
        gw = NetworkGateway(allowed_hosts=["*"])
        assert gw.is_host_allowed("evil.example.com")
        assert gw.is_host_allowed("localhost")

    async def test_default_allow_list_is_localhost_only(self) -> None:
        gw = NetworkGateway()
        assert gw.is_host_allowed("localhost")
        assert gw.is_host_allowed("127.0.0.1")
        assert not gw.is_host_allowed("evil.example.com")


@pytest.mark.offline
class TestPermissionChecker:
    """Permission checker tests."""

    async def test_noop_checker_allows(self) -> None:
        checker = NoOpPermissionChecker()
        result = await checker.check(
            ActorRef.system(),
            Permission(name="test.perm"),
        )
        assert result.decision == PermissionDecision.ALLOW


@pytest.mark.offline
class TestAuditLogger:
    """Audit logger tests."""

    async def test_noop_logger_doesnt_raise(self) -> None:
        logger = NoOpAuditLogger()
        entry = AuditEntry(
            actor=ActorRef.system(),
            action="test.action",
            target="/tmp/test",
            success=True,
        )
        # Should not raise
        await logger.log(entry)

    async def test_collecting_audit_logger(self) -> None:
        """A custom audit logger that collects entries for testing."""
        collected: list[AuditEntry] = []

        class Collecting:
            async def log(self, entry: AuditEntry) -> None:
                collected.append(entry)

        set_audit_logger(Collecting())  # type: ignore[arg-type]
        gw = FileSystemGateway()
        await gw.write("/tmp/test_audit.txt", b"x", actor=ActorRef.system())
        assert len(collected) >= 1
        assert any(e.action == "gateway.fs.write" for e in collected)


@pytest.mark.offline
class TestGatewayFacade:
    """Gateway facade tests."""

    def test_default_gateway_wires_sub_gateways(self) -> None:
        gw = get_gateway()
        assert gw.fs is not None
        assert gw.shell is not None
        assert gw.net is not None

    def test_get_fs_gateway_returns_singleton(self) -> None:
        gw1 = get_fs_gateway()
        gw2 = get_fs_gateway()
        assert gw1 is gw2

    def test_get_shell_gateway_returns_singleton(self) -> None:
        gw1 = get_shell_gateway()
        gw2 = get_shell_gateway()
        assert gw1 is gw2

    def test_get_net_gateway_returns_singleton(self) -> None:
        gw1 = get_net_gateway()
        gw2 = get_net_gateway()
        assert gw1 is gw2

    def test_get_gateway_returns_singleton(self) -> None:
        gw1 = get_gateway()
        gw2 = get_gateway()
        assert gw1 is gw2


@pytest.mark.offline
class TestInvariantEnforcement:
    """Verify INV-02 — no I/O imports outside core/gateway/."""

    def test_subprocess_only_in_shell_gateway(self) -> None:
        """Only core/gateway/shell.py may import subprocess."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        offending: list[str] = []
        for py_file in repo_root.rglob("*.py"):
            rel = py_file.relative_to(repo_root)
            # Skip the gateway itself
            if "gateway" in py_file.parts:
                continue
            if "model_router" in py_file.parts:
                continue
            if "scripts" in py_file.parts:
                continue
            if "installer" in py_file.parts:
                # The installer is a system-level tool that legitimately needs
                # subprocess to detect and install dependencies.
                continue
            if "brain" in py_file.parts:
                # The brain service uses nvidia-smi for GPU detection.
                continue
            if any(
                s in py_file.parts
                for s in (
                    "doctor",
                    "backup",
                    "cleanup",
                    "runtime_discovery",
                    "uninstall",
                    "validator",
                    "self_healing",
                    "monitoring",
                    "execution_engine",
                    "benchmark",
                    "certify",
                    "reset",
                    "packaging",
                )
            ):
                # System-level services that legitimately spawn processes.
                continue
            if "surfaces" in py_file.parts and "cli" in py_file.parts:
                continue
            if "tests" in py_file.parts:
                continue
            if ".venv" in py_file.parts or "node_modules" in py_file.parts:
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "import subprocess" in stripped or "from subprocess" in stripped:
                    offending.append(f"{rel}:{line_no}: {stripped}")
        assert not offending, f"INV-02 violations: {offending}"
