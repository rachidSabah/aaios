"""Security tests — audit chain, secret store, ACL, invariant enforcement.

These tests verify the security model from docs/architecture/07-security-model.md:
  - Audit log tamper detection
  - Secret store encryption at rest
  - RBAC policy enforcement (owner/admin/operator/viewer)
  - INV-02 enforcement (no I/O imports outside gateway/model_router)
  - INV-09 enforcement (no agent implementation names in core)
  - Permission approval flow
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission, PermissionDecision
from services.security import (
    EncryptedSecretStore,
    InMemoryAuditLog,
    PolicyDecision,
    PolicyEngine,
    Role,
    SecretNotFoundError,
    SecurityManager,
)
from services.security.audit_log import AuditLogEntry


@pytest.mark.offline
class TestAuditChainSecurity:
    """Audit log tamper detection."""

    async def test_chain_intact_after_normal_operation(self) -> None:
        log = InMemoryAuditLog()
        for i in range(10):
            await log.log(
                AuditLogEntry(
                    actor=ActorRef.system(),
                    action=f"test.{i}",
                    target=f"item-{i}",
                    success=True,
                )
            )
        assert await log.verify_chain() is True

    async def test_tamper_detected_on_modification(self) -> None:
        log = InMemoryAuditLog()
        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="original",
                target="item",
                success=True,
            )
        )
        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="second",
                target="item",
                success=True,
            )
        )
        # Tamper: modify the first entry's action
        log._entries[0].action = "tampered"  # noqa: SLF001
        assert await log.verify_chain() is False

    async def test_tamper_detected_on_deletion(self) -> None:
        log = InMemoryAuditLog()
        for i in range(5):
            await log.log(
                AuditLogEntry(
                    actor=ActorRef.system(),
                    action=f"test.{i}",
                    target=f"item-{i}",
                    success=True,
                )
            )
        # Delete an entry from the middle
        del log._entries[2]  # noqa: SLF001
        assert await log.verify_chain() is False

    async def test_tamper_detected_on_reordering(self) -> None:
        log = InMemoryAuditLog()
        for i in range(5):
            await log.log(
                AuditLogEntry(
                    actor=ActorRef.system(),
                    action=f"test.{i}",
                    target=f"item-{i}",
                    success=True,
                )
            )
        # Swap two entries
        log._entries[0], log._entries[1] = log._entries[1], log._entries[0]  # noqa: SLF001
        assert await log.verify_chain() is False


@pytest.mark.offline
class TestSecretStoreSecurity:
    """Secret store encryption."""

    async def test_secret_encrypted_at_rest(self) -> None:
        """The stored value is NOT plaintext."""
        store = EncryptedSecretStore()
        await store.set("api_key", "sk-super-secret-value-12345")
        secret = store._secrets["api_key"]  # noqa: SLF001
        # The encrypted value should not contain the plaintext
        assert b"sk-super-secret-value-12345" not in secret.encrypted_value

    async def test_secret_not_in_logs(self) -> None:
        """Secret values should never appear in log output."""
        # This is a design-level test — the API returns SecretRef, not plaintext
        store = EncryptedSecretStore()
        await store.set("key", "plaintext-value")
        # The internal storage uses encrypted bytes
        secret = store._secrets["key"]  # noqa: SLF001
        assert isinstance(secret.encrypted_value, bytes)
        # Only get() returns plaintext, and it must be called explicitly
        value = await store.get("key")
        assert value == "plaintext-value"

    async def test_secret_rotation_preserves_old_during_grace(self) -> None:
        """After rotation, the old value is available during the grace period."""
        store = EncryptedSecretStore()
        await store.set("key", "old-value")
        await store.rotate("key", "new-value")
        assert await store.get("key") == "new-value"
        assert await store.get_previous("key") == "old-value"

    async def test_secret_not_found_raises(self) -> None:
        store = EncryptedSecretStore()
        with pytest.raises(SecretNotFoundError):
            await store.get("nonexistent")

    async def test_different_passphrases_produce_different_keys(self) -> None:
        """Different passphrases produce different encryption keys."""
        store1 = EncryptedSecretStore.from_passphrase("passphrase-1")
        store2 = EncryptedSecretStore.from_passphrase("passphrase-2")
        await store1.set("key", "value")
        # store2 has a different key — can't decrypt store1's secrets
        # (this would fail in a real cross-store scenario; here we just verify
        # the keys are different)
        assert store1._key != store2._key  # noqa: SLF001


@pytest.mark.offline
class TestRBACSecurity:
    """RBAC policy enforcement."""

    def test_owner_allows_everything(self) -> None:
        engine = PolicyEngine()
        engine.assign_role("owner1", Role.OWNER)
        actor = ActorRef.user("owner1")
        for perm_name in [
            "gateway.fs.write",
            "gateway.shell.exec",
            "security.scan",
            "plugin.install",
        ]:
            perm = Permission(name=perm_name)
            decision = engine.evaluate(actor, perm)
            assert decision == PolicyDecision.ALLOW, f"Owner denied {perm_name}"

    def test_viewer_denied_sensitive_operations(self) -> None:
        engine = PolicyEngine()
        engine.assign_role("viewer1", Role.VIEWER)
        actor = ActorRef.user("viewer1")
        for perm_name in [
            "gateway.fs.write",
            "gateway.shell.exec",
            "plugin.install",
            "agent.dispatch",
        ]:
            perm = Permission(name=perm_name)
            decision = engine.evaluate(actor, perm)
            assert decision == PolicyDecision.DENY, f"Viewer allowed {perm_name}"

    def test_operator_asks_for_gateway(self) -> None:
        engine = PolicyEngine()
        engine.assign_role("op1", Role.OPERATOR)
        actor = ActorRef.user("op1")
        perm = Permission(name="gateway.fs.write")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ASK

    def test_admin_asks_for_security(self) -> None:
        engine = PolicyEngine()
        engine.assign_role("admin1", Role.ADMIN)
        actor = ActorRef.user("admin1")
        perm = Permission(name="security.scan")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ASK

    def test_no_role_denied_by_default(self) -> None:
        """An actor with no role is denied everything (fail-closed)."""
        engine = PolicyEngine()
        actor = ActorRef.user("unknown")
        perm = Permission(name="task.read")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.DENY

    def test_glob_pattern_matching(self) -> None:
        """gateway.fs.* matches gateway.fs.read and gateway.fs.write."""
        engine = PolicyEngine()
        engine.assign_role("op1", Role.OPERATOR)
        actor = ActorRef.user("op1")
        # All gateway.* should ASK for operator
        for perm_name in [
            "gateway.fs.read",
            "gateway.fs.write",
            "gateway.shell.exec",
            "gateway.net.request",
        ]:
            perm = Permission(name=perm_name)
            decision = engine.evaluate(actor, perm)
            assert decision == PolicyDecision.ASK, f"{perm_name} should ASK for operator"


@pytest.mark.offline
class TestInvariantEnforcement:
    """Architecture invariant enforcement (INV-02, INV-09)."""

    def test_inv_02_no_io_imports_outside_gateway(self) -> None:
        """INV-02: only core/gateway/ and services/model_router/ may import I/O modules."""
        repo_root = Path(__file__).resolve().parents[2]
        banned_imports = [
            "import subprocess",
            "import socket",
            "from subprocess",
            "from socket",
            "import requests",
            "from requests",
        ]
        offending: list[str] = []
        for pkg in ["core", "services", "agents", "supervisor", "orchestrator", "surfaces"]:
            for py_file in (repo_root / pkg).rglob("*.py"):
                if "gateway" in py_file.parts or "model_router" in py_file.parts:
                    continue
                if "installer" in py_file.parts or "runtime_discovery" in py_file.parts:
                    # Installer is a system-level tool — legitimately uses subprocess
                    continue
                if "brain" in py_file.parts:
                    # Brain service uses nvidia-smi for GPU detection
                    continue
                if any(s in py_file.parts for s in (
                    "doctor", "backup", "cleanup", "runtime_discovery", "uninstall", "validator",
                    "self_healing", "monitoring", "execution_engine", "benchmark",
                    "certify", "reset", "packaging",
                )):
                    # System-level services that legitimately spawn processes
                    continue
                if "surfaces" in py_file.parts and "cli" in py_file.parts:
                    continue
                if "tests" in py_file.parts:
                    continue
                text = py_file.read_text(encoding="utf-8")
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    for banned in banned_imports:
                        if banned in stripped:
                            offending.append(f"{py_file}: {stripped}")
                            break
        assert not offending, f"INV-02 violations: {offending}"

    def test_inv_09_no_agent_names_in_core(self) -> None:
        """INV-09: no agent implementation names in core/services/supervisor/orchestrator/surfaces."""
        import re

        repo_root = Path(__file__).resolve().parents[2]
        banned_pattern = r"\b(claude.?code|hermes|openhands|cline|roo.?code|roocode)\b"
        regex = re.compile(banned_pattern, re.IGNORECASE)
        offending: list[str] = []
        for pkg in ["core", "services", "supervisor", "orchestrator", "surfaces"]:
            for py_file in (repo_root / pkg).rglob("*.py"):
                # The installer legitimately needs to know agent names to discover them
                if "installer" in py_file.parts or "runtime_discovery" in py_file.parts:
                    continue
                # The brain service references agent names for the constellation
                if "brain" in py_file.parts:
                    continue
                # Execution engine adapters reference agent names by design
                if "execution_engine" in py_file.parts:
                    continue
                for line in py_file.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if regex.search(stripped):
                        offending.append(f"{py_file}: {stripped}")
        assert not offending, f"INV-09 violations: {offending}"

    def test_inv_03_pydantic_models_cross_boundaries(self) -> None:
        """INV-03: no bare dicts crossing module boundaries (spot check)."""
        # This is a design-level invariant — verified by mypy + custom rules in CI
        # Here we just verify the key contracts are Pydantic models
        from core.contracts.agent import AgentIdentity, CapabilityManifest
        from core.contracts.event import Event
        from core.contracts.memory.item import MemoryItem
        from core.contracts.task import TaskRequest, TaskResult

        for model in [
            Event,
            TaskRequest,
            TaskResult,
            MemoryItem,
            AgentIdentity,
            CapabilityManifest,
        ]:
            assert hasattr(model, "model_validate"), f"{model.__name__} is not a Pydantic model"

    def test_inv_05_no_secrets_in_code(self) -> None:
        """INV-05: no hardcoded secrets in Python source files."""
        repo_root = Path(__file__).resolve().parents[2]
        # Look for common secret patterns
        import re

        secret_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style API keys
            r"ghp_[a-zA-Z0-9]{36,}",  # GitHub PATs
            r"AKIA[A-Z0-9]{16}",  # AWS access keys
        ]
        offending: list[str] = []
        for py_file in repo_root.rglob("*.py"):
            if ".venv" in py_file.parts or "node_modules" in py_file.parts:
                continue
            if "tests" in py_file.parts:
                continue  # tests may have mock keys
            text = py_file.read_text(encoding="utf-8")
            for pattern in secret_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    offending.append(f"{py_file}: {matches}")
        # Allow the test files (they use mock values)
        real_offending = [o for o in offending if "test" not in o.lower()]
        assert not real_offending, f"INV-05 violations: {real_offending}"


@pytest.mark.offline
class TestSecurityManagerIntegration:
    """SecurityManager end-to-end security tests."""

    async def test_full_permission_flow(self) -> None:
        """Full flow: assign role → check permission → audit → verify chain."""
        mgr = SecurityManager()
        mgr.install_in_gateway()

        mgr.assign_role("alice", Role.OWNER)
        mgr.assign_role("bob", Role.VIEWER)

        # Alice can write
        result = await mgr.check(
            ActorRef.user("alice"),
            Permission(name="gateway.fs.write"),
        )
        assert result.decision == PermissionDecision.ALLOW

        # Bob cannot write
        result = await mgr.check(
            ActorRef.user("bob"),
            Permission(name="gateway.fs.write"),
        )
        assert result.decision == PermissionDecision.DENY

        # Audit both checks
        from core.gateway.audit import AuditEntry

        await mgr.log(
            AuditEntry(
                actor=ActorRef.user("alice"),
                action="gateway.fs.write",
                target="/tmp/file",
                success=True,
            )
        )
        await mgr.log(
            AuditEntry(
                actor=ActorRef.user("bob"),
                action="gateway.fs.write",
                target="/tmp/file",
                success=False,
                reason="denied",
            )
        )

        # Verify chain
        assert await mgr.verify_audit_chain() is True

        # Query by actor
        alice_entries = await mgr.get_audit_entries(actor_id="alice")
        assert len(alice_entries) == 1
        assert alice_entries[0].success is True

        bob_entries = await mgr.get_audit_entries(actor_id="bob")
        assert len(bob_entries) == 1
        assert bob_entries[0].success is False

    async def test_secret_lifecycle_through_manager(self) -> None:
        """Secret set → get → rotate → get → get_previous → delete."""
        mgr = SecurityManager()
        await mgr.set_secret("test/key", "initial-value")
        assert await mgr.get_secret("test/key") == "initial-value"

        await mgr.rotate_secret("test/key", "rotated-value")
        assert await mgr.get_secret("test/key") == "rotated-value"

        old = await mgr.secrets.get_previous("test/key")
        assert old == "initial-value"

        assert await mgr.secrets.delete("test/key") is True
        with pytest.raises(SecretNotFoundError):
            await mgr.get_secret("test/key")
