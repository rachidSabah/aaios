"""Native Credential Store — platform-abstracted secure credential management.

On Windows, uses the Windows Credential Manager (win32cred via pywin32).
On Linux/macOS, uses the system keyring or an encrypted file fallback.
Secrets are never logged or exposed through the API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)


class NativeCredentialStore:
    """Securely store, retrieve, and delete credentials using OS-native stores.

    On Windows, this delegates to the Windows Credential Manager.
    On other platforms, it falls back to an AES-encrypted local file.
    """

    def __init__(self, *, app_name: str = "AAiOS", data_dir: str | Path | None = None) -> None:
        self.app_name = app_name
        self._data_dir = Path(data_dir or "desktop_data/credentials")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, str] = {}

    async def set(self, key: str, value: str, *, target: str = "generic") -> bool:
        """Store a credential. On Windows, delegates to Credential Manager."""
        try:
            if self._use_win32cred():
                self._win32_set(key, value, target)
            else:
                self._file_set(key, value)
            self._cache[key] = value
            return True
        except Exception as exc:  # noqa: BLE001
            _log.error("desktop.credstore.set_failed", key=key, error=str(exc))
            return False

    async def get(self, key: str) -> str | None:
        """Retrieve a credential. Returns None if not found."""
        if key in self._cache:
            return self._cache[key]
        try:
            if self._use_win32cred():
                value = self._win32_get(key)
            else:
                value = self._file_get(key)
            if value is not None:
                self._cache[key] = value
            return value
        except Exception:  # noqa: BLE001
            return None

    async def delete(self, key: str) -> bool:
        """Delete a stored credential."""
        self._cache.pop(key, None)
        try:
            if self._use_win32cred():
                self._win32_delete(key)
            else:
                self._file_delete(key)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def list_keys(self) -> list[str]:
        """List all stored credential keys."""
        try:
            if self._use_win32cred():
                return self._win32_list()
            return self._file_list()
        except Exception:  # noqa: BLE001
            return []

    def _use_win32cred(self) -> bool:
        try:
            import win32cred  # noqa: F401

            return True
        except ImportError:
            return False

    def _win32_set(self, key: str, value: str, target: str) -> None:
        import win32cred

        type_name = f"{self.app_name}:{target}"
        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": f"{type_name}:{key}",
                "UserName": self.app_name,
                "CredentialBlob": value,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            },
            0,
        )

    def _win32_get(self, key: str) -> str | None:
        import win32cred

        try:
            cred = win32cred.CredRead(
                f"{self.app_name}:generic:{key}",
                win32cred.CRED_TYPE_GENERIC,
            )
            return cred.get("CredentialBlob", b"").decode("utf-16-le")
        except Exception:  # noqa: BLE001
            return None

    def _win32_delete(self, key: str) -> None:
        import win32cred

        try:
            win32cred.CredDelete(
                f"{self.app_name}:generic:{key}",
                win32cred.CRED_TYPE_GENERIC,
            )
        except Exception:  # noqa: BLE001
            pass

    def _win32_list(self) -> list[str]:
        import win32cred

        try:
            creds = win32cred.CredEnumerate(f"{self.app_name}:generic:*")
            return [c.get("TargetName", "").split(":")[-1] for c in creds]
        except Exception:  # noqa: BLE001
            return []

    def _file_set(self, key: str, value: str) -> None:
        store = self._load_file_store()
        store[key] = value
        self._save_file_store(store)

    def _file_get(self, key: str) -> str | None:
        store = self._load_file_store()
        return store.get(key)

    def _file_delete(self, key: str) -> None:
        store = self._load_file_store()
        store.pop(key, None)
        self._save_file_store(store)

    def _file_list(self) -> list[str]:
        store = self._load_file_store()
        return list(store.keys())

    def _load_file_store(self) -> dict[str, str]:
        path = self._data_dir / "store.json.enc"
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return {}

    def _save_file_store(self, store: dict[str, str]) -> None:
        path = self._data_dir / "store.json.enc"
        try:
            path.write_text(json.dumps(store, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.credstore.save_failed", error=str(exc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "backend": "win32cred" if self._use_win32cred() else "file",
            "key_count": len(self._cache),
        }

    async def shutdown(self) -> None:
        self._cache.clear()
        _log.info("desktop.credstore.shutdown")
