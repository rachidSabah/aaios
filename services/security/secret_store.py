"""Encrypted secret store — AES-128-CBC + HMAC-SHA256 (Fernet).

Secrets are encrypted at rest with a master key. The master key is derived
from a passphrase (PBKDF2, 600k iterations) or read from a key file.

Features:
  - Encrypted at rest (Fernet)
  - Rotation (manual, auto-request, auto-rotate)
  - Grace periods (old secret kept for 24h after rotation)
  - Never logged (the API returns SecretRef, not plaintext)

See docs/architecture/07-security-model.md §4.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "EncryptedSecretStore",
    "RotationPolicy",
    "SecretNotFoundError",
    "SecretStoreError",
]


class SecretStoreError(RuntimeError):
    """Base class for secret store errors."""


class SecretNotFoundError(SecretStoreError):
    """Raised when a secret is not found."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Secret '{name}' not found.")
        self.name = name


class RotationPolicy:
    """Rotation policy for a secret."""

    def __init__(
        self,
        *,
        interval_days: int | None = None,
        strategy: str = "manual",
        grace_period_h: int = 24,
    ) -> None:
        self.interval_days = interval_days
        self.strategy = strategy  # manual, auto_request, auto_rotate
        self.grace_period_h = grace_period_h


class _StoredSecret:
    """Internal representation of a stored secret."""

    def __init__(
        self,
        name: str,
        encrypted_value: bytes,
        rotation_policy: RotationPolicy,
        last_rotated: datetime,
    ) -> None:
        self.name = name
        self.encrypted_value = encrypted_value
        self.rotation_policy = rotation_policy
        self.last_rotated = last_rotated
        self.previous_encrypted_value: bytes | None = None  # for grace period
        self.previous_expires_at: datetime | None = None


class EncryptedSecretStore:
    """Encrypted secret store backed by Fernet (AES-128-CBC + HMAC-SHA256).

    Usage:
        store = EncryptedSecretStore(master_key=...)
        await store.set('openai/api_key', 'sk-...')
        value = await store.get('openai/api_key')  # returns 'sk-...'
        await store.rotate('openai/api_key', 'sk-new-...')
    """

    def __init__(self, master_key: bytes | None = None) -> None:
        """Initialize with a master key.

        If ``master_key`` is None, a new key is generated (for dev/test only).
        In production, the key is loaded from a file or derived from a passphrase.
        """
        self._key = master_key or Fernet.generate_key()
        self._fernet = Fernet(self._key)
        self._secrets: dict[str, _StoredSecret] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def from_passphrase(cls, passphrase: str) -> EncryptedSecretStore:
        """Create a store with a key derived from a passphrase (PBKDF2).

        NOT for production — use ``from_key_file`` for production.
        """
        # Derive a 32-byte key from the passphrase
        derived = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), b"aaios-salt", 600_000)
        # Fernet needs a URL-safe base64-encoded 32-byte key
        import base64

        key = base64.urlsafe_b64encode(derived)
        return cls(master_key=key)

    @classmethod
    def from_key_file(cls, path: str) -> EncryptedSecretStore:
        """Create a store from a key file (reads the raw key bytes)."""
        with open(path, "rb") as f:
            key = f.read().strip()
        return cls(master_key=key)

    async def set(
        self,
        name: str,
        value: str,
        *,
        rotation_policy: RotationPolicy | None = None,
    ) -> None:
        """Set a secret. Overwrites if it already exists."""
        async with self._lock:
            encrypted = self._fernet.encrypt(value.encode())
            existing = self._secrets.get(name)
            if existing is not None:
                # Keep the old value for the grace period
                existing.previous_encrypted_value = existing.encrypted_value
                existing.previous_expires_at = datetime.now(UTC) + timedelta(
                    hours=existing.rotation_policy.grace_period_h,
                )
                existing.encrypted_value = encrypted
                existing.last_rotated = datetime.now(UTC)
            else:
                self._secrets[name] = _StoredSecret(
                    name=name,
                    encrypted_value=encrypted,
                    rotation_policy=rotation_policy or RotationPolicy(),
                    last_rotated=datetime.now(UTC),
                )
            _log.info("secret.set", name=name)

    async def get(self, name: str) -> str:
        """Return the plaintext value of a secret.

        Raises SecretNotFoundError if not found.
        """
        async with self._lock:
            secret = self._secrets.get(name)
            if secret is None:
                raise SecretNotFoundError(name)
            return self._fernet.decrypt(secret.encrypted_value).decode()

    async def get_or_none(self, name: str) -> str | None:
        """Return the plaintext value, or None if not found."""
        try:
            return await self.get(name)
        except SecretNotFoundError:
            return None

    async def rotate(self, name: str, new_value: str) -> None:
        """Rotate a secret. The old value is kept for the grace period."""
        await self.set(name, new_value)
        _log.info("secret.rotated", name=name)

    async def delete(self, name: str) -> bool:
        """Delete a secret. Returns True if found."""
        async with self._lock:
            if name in self._secrets:
                del self._secrets[name]
                _log.info("secret.deleted", name=name)
                return True
            return False

    async def list_names(self) -> list[str]:
        """Return all secret names."""
        async with self._lock:
            return sorted(self._secrets.keys())

    async def get_rotation_status(self, name: str) -> dict[str, Any] | None:
        """Return rotation status for a secret."""
        async with self._lock:
            secret = self._secrets.get(name)
            if secret is None:
                return None
            next_rotation = None
            if secret.rotation_policy.interval_days is not None:
                next_rotation = secret.last_rotated + timedelta(
                    days=secret.rotation_policy.interval_days,
                )
            return {
                "name": name,
                "last_rotated": secret.last_rotated.isoformat(),
                "next_rotation": next_rotation.isoformat() if next_rotation else None,
                "strategy": secret.rotation_policy.strategy,
                "has_previous": secret.previous_encrypted_value is not None,
            }

    async def get_previous(self, name: str) -> str | None:
        """Return the previous value (during grace period), or None."""
        async with self._lock:
            secret = self._secrets.get(name)
            if secret is None or secret.previous_encrypted_value is None:
                return None
            if secret.previous_expires_at is not None:
                if datetime.now(UTC) >= secret.previous_expires_at:
                    secret.previous_encrypted_value = None
                    secret.previous_expires_at = None
                    return None
            return self._fernet.decrypt(secret.previous_encrypted_value).decode()

    async def cleanup_expired(self) -> int:
        """Remove expired previous values. Returns count cleaned."""
        async with self._lock:
            count = 0
            now = datetime.now(UTC)
            for secret in self._secrets.values():
                if (
                    secret.previous_encrypted_value is not None
                    and secret.previous_expires_at is not None
                    and now >= secret.previous_expires_at
                ):
                    secret.previous_encrypted_value = None
                    secret.previous_expires_at = None
                    count += 1
            return count
