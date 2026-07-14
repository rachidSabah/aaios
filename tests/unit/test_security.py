"""Tests for the Security Layer — policy engine, secret store, audit log, manager."""

from __future__ import annotations

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


@pytest.mark.offline
class TestPolicyEngine:
    """PolicyEngine tests."""

    def test_owner_can_do_everything(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("alice")
        engine.assign_role("alice", Role.OWNER)
        perm = Permission(name="gateway.fs.write")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ALLOW

    def test_viewer_denied_by_default(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("viewer1")
        engine.assign_role("viewer1", Role.VIEWER)
        perm = Permission(name="gateway.fs.write")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.DENY

    def test_viewer_can_read_tasks(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("viewer1")
        engine.assign_role("viewer1", Role.VIEWER)
        perm = Permission(name="task.read")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ALLOW

    def test_operator_asked_for_gateway(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("op1")
        engine.assign_role("op1", Role.OPERATOR)
        perm = Permission(name="gateway.fs.write")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ASK

    def test_operator_can_submit_tasks(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("op1")
        engine.assign_role("op1", Role.OPERATOR)
        perm = Permission(name="task.submit")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ALLOW

    def test_admin_asked_for_security(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("admin1")
        engine.assign_role("admin1", Role.ADMIN)
        perm = Permission(name="security.scan")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.ASK

    def test_no_role_denied(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("unknown")
        perm = Permission(name="task.read")
        decision = engine.evaluate(actor, perm)
        assert decision == PolicyDecision.DENY

    def test_glob_match(self) -> None:
        engine = PolicyEngine()
        actor = ActorRef.user("op1")
        engine.assign_role("op1", Role.OPERATOR)
        # gateway.* should match gateway.fs.write
        perm = Permission(name="gateway.fs.write")
        decision = engine.evaluate(actor, perm, resource="*")
        assert decision == PolicyDecision.ASK


@pytest.mark.offline
class TestEncryptedSecretStore:
    """EncryptedSecretStore tests."""

    async def test_set_and_get(self) -> None:
        store = EncryptedSecretStore()
        await store.set("openai/api_key", "sk-test-123")
        value = await store.get("openai/api_key")
        assert value == "sk-test-123"

    async def test_get_not_found(self) -> None:
        store = EncryptedSecretStore()
        with pytest.raises(SecretNotFoundError):
            await store.get("nonexistent")

    async def test_get_or_none(self) -> None:
        store = EncryptedSecretStore()
        assert await store.get_or_none("nonexistent") is None
        await store.set("foo", "bar")
        assert await store.get_or_none("foo") == "bar"

    async def test_rotate(self) -> None:
        store = EncryptedSecretStore()
        await store.set("key", "old-value")
        await store.rotate("key", "new-value")
        assert await store.get("key") == "new-value"
        # Previous value should be available during grace period
        prev = await store.get_previous("key")
        assert prev == "old-value"

    async def test_delete(self) -> None:
        store = EncryptedSecretStore()
        await store.set("key", "value")
        assert await store.delete("key") is True
        assert await store.delete("key") is False

    async def test_list_names(self) -> None:
        store = EncryptedSecretStore()
        await store.set("a", "1")
        await store.set("b", "2")
        names = await store.list_names()
        assert set(names) == {"a", "b"}

    async def test_encrypted_at_rest(self) -> None:
        """The stored value is encrypted — not plaintext."""
        store = EncryptedSecretStore()
        await store.set("key", "plaintext-secret")
        # The internal encrypted_value should NOT contain 'plaintext-secret'
        secret = store._secrets["key"]  # noqa: SLF001
        assert b"plaintext-secret" not in secret.encrypted_value

    async def test_from_passphrase(self) -> None:
        store = EncryptedSecretStore.from_passphrase("my-passphrase")
        await store.set("key", "value")
        assert await store.get("key") == "value"

    async def test_rotation_status(self) -> None:
        from services.security.secret_store import RotationPolicy

        store = EncryptedSecretStore()
        await store.set("key", "value", rotation_policy=RotationPolicy(interval_days=30))
        status = await store.get_rotation_status("key")
        assert status is not None
        assert status["strategy"] == "manual"
        assert status["next_rotation"] is not None


@pytest.mark.offline
class TestAuditLog:
    """InMemoryAuditLog tests."""

    async def test_log_and_count(self) -> None:
        log = InMemoryAuditLog()
        actor = ActorRef.system()
        from services.security.audit_log import AuditLogEntry

        entry = AuditLogEntry(actor=actor, action="test.action", target="test", success=True)
        await log.log(entry)
        assert await log.count() == 1

    async def test_hash_chain(self) -> None:
        """Each entry's hash includes the previous entry's hash."""
        log = InMemoryAuditLog()
        from services.security.audit_log import AuditLogEntry

        for i in range(3):
            await log.log(
                AuditLogEntry(
                    actor=ActorRef.system(),
                    action=f"test.{i}",
                    target=f"item-{i}",
                    success=True,
                )
            )
        # Verify the chain
        assert await log.verify_chain() is True

    async def test_tamper_detection(self) -> None:
        """Modifying an entry breaks the hash chain."""
        log = InMemoryAuditLog()
        from services.security.audit_log import AuditLogEntry

        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="test.0",
                target="item-0",
                success=True,
            )
        )
        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="test.1",
                target="item-1",
                success=True,
            )
        )
        # Tamper: modify the first entry
        log._entries[0].action = "tampered"  # noqa: SLF001
        assert await log.verify_chain() is False

    async def test_filter_by_actor(self) -> None:
        log = InMemoryAuditLog()
        from services.security.audit_log import AuditLogEntry

        await log.log(
            AuditLogEntry(
                actor=ActorRef.user("alice"),
                action="test",
                target="x",
                success=True,
            )
        )
        await log.log(
            AuditLogEntry(
                actor=ActorRef.user("bob"),
                action="test",
                target="x",
                success=True,
            )
        )
        alice_entries = await log.get_entries(actor_id="alice")
        assert len(alice_entries) == 1
        assert all(e.actor.id == "alice" for e in alice_entries)

    async def test_filter_by_action(self) -> None:
        log = InMemoryAuditLog()
        from services.security.audit_log import AuditLogEntry

        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="gateway.fs.read",
                target="x",
                success=True,
            )
        )
        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="gateway.fs.write",
                target="x",
                success=True,
            )
        )
        reads = await log.get_entries(action="gateway.fs.read")
        assert len(reads) == 1

    async def test_export(self) -> None:
        log = InMemoryAuditLog()
        from services.security.audit_log import AuditLogEntry

        await log.log(
            AuditLogEntry(
                actor=ActorRef.system(),
                action="test",
                target="x",
                success=True,
            )
        )
        exported = await log.export()
        assert len(exported) == 1
        assert "hash" in exported[0]
        assert "previous_hash" in exported[0]


@pytest.mark.offline
class TestSecurityManager:
    """SecurityManager tests."""

    async def test_check_allows_owner(self) -> None:
        mgr = SecurityManager()
        mgr.assign_role("alice", Role.OWNER)
        actor = ActorRef.user("alice")
        perm = Permission(name="gateway.fs.write")
        result = await mgr.check(actor, perm)
        assert result.decision == PermissionDecision.ALLOW

    async def test_check_denies_no_role(self) -> None:
        mgr = SecurityManager()
        actor = ActorRef.user("unknown")
        perm = Permission(name="gateway.fs.write")
        result = await mgr.check(actor, perm)
        assert result.decision == PermissionDecision.DENY

    async def test_check_asks_operator(self) -> None:
        mgr = SecurityManager()
        mgr.assign_role("op1", Role.OPERATOR)
        actor = ActorRef.user("op1")
        perm = Permission(name="gateway.fs.write")
        result = await mgr.check(actor, perm)
        assert result.decision == PermissionDecision.ASK

    async def test_audit_log(self) -> None:
        from core.gateway.audit import AuditEntry

        mgr = SecurityManager()
        entry = AuditEntry(
            actor=ActorRef.system(),
            action="test.action",
            target="/tmp/test",
            success=True,
        )
        await mgr.log(entry)
        entries = await mgr.get_audit_entries()
        assert len(entries) == 1
        assert entries[0].action == "test.action"

    async def test_secrets(self) -> None:
        mgr = SecurityManager()
        await mgr.set_secret("key", "value")
        assert await mgr.get_secret("key") == "value"

    async def test_verify_audit_chain(self) -> None:
        from core.gateway.audit import AuditEntry

        mgr = SecurityManager()
        for i in range(5):
            await mgr.log(
                AuditEntry(
                    actor=ActorRef.system(),
                    action=f"test.{i}",
                    target=f"item-{i}",
                    success=True,
                )
            )
        assert await mgr.verify_audit_chain() is True

    async def test_install_in_gateway(self) -> None:
        """SecurityManager can be installed as the Gateway's checker + logger."""
        from core.gateway import get_audit_logger, get_permission_checker

        mgr = SecurityManager()
        mgr.install_in_gateway()
        # The Gateway should now return the SecurityManager
        checker = get_permission_checker()
        logger = get_audit_logger()
        assert checker is mgr
        assert logger is mgr
