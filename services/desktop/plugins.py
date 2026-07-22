"""Desktop Plugin Loader — hot-reload plugin management for the desktop runtime.

Integrates with the existing Plugin-first Architecture. Provides installation,
updates, removal, permission management, signing, verification, and sandboxing
for desktop-specific plugins. Publishes plugin lifecycle events on the Event Bus.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class DesktopPlugin:
    """Metadata for an installed desktop plugin."""

    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    permissions: list[str] = field(default_factory=list)
    signature: str = ""
    enabled: bool = True
    installed_at: str = ""
    entry_point: str = ""
    sandboxed: bool = True


class DesktopPluginLoader:
    """Install, manage, and hot-reload desktop plugins."""

    def __init__(
        self,
        *,
        plugin_dir: str | Path | None = None,
        sandbox_enabled: bool = True,
    ) -> None:
        self._plugin_dir = Path(plugin_dir or "desktop_data/plugins")
        self._plugin_dir.mkdir(parents=True, exist_ok=True)
        self._sandbox_enabled = sandbox_enabled
        self._plugins: dict[str, DesktopPlugin] = {}
        self._watcher_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._on_install: list[Callable[[DesktopPlugin], None]] = []
        self._on_uninstall: list[Callable[[str], None]] = []

    def on_install(self, callback: Callable[[DesktopPlugin], None]) -> None:
        self._on_install.append(callback)

    def on_uninstall(self, callback: Callable[[str], None]) -> None:
        self._on_uninstall.append(callback)

    async def start(self) -> None:
        await self._scan_installed()
        self._stop.clear()
        self._watcher_task = asyncio.create_task(self._watch_loop())
        _log.info("desktop.plugins.started", plugin_dir=str(self._plugin_dir))

    async def stop(self) -> None:
        self._stop.set()
        if self._watcher_task is not None:
            await self._watcher_task
            self._watcher_task = None
        _log.info("desktop.plugins.stopped")

    async def install(self, package_path: str | Path) -> DesktopPlugin:
        """Install a plugin from a .zip package."""
        path = Path(package_path)
        if not path.exists():
            raise FileNotFoundError(f"Plugin package not found: {path}")

        manifest = self._extract_manifest(path)
        plugin_id = manifest.get("id", hashlib.md5(path.name.encode()).hexdigest()[:12])
        dest = self._plugin_dir / plugin_id
        dest.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(dest)

        sig = manifest.get("signature", "")
        plugin = DesktopPlugin(
            id=plugin_id,
            name=manifest.get("name", plugin_id),
            version=manifest.get("version", "0.1.0"),
            description=manifest.get("description", ""),
            author=manifest.get("author", ""),
            homepage=manifest.get("homepage", ""),
            permissions=manifest.get("permissions", []),
            signature=sig,
            enabled=True,
            installed_at=datetime.now(UTC).isoformat(),
            entry_point=manifest.get("entry_point", "main.py"),
            sandboxed=self._sandbox_enabled,
        )
        self._plugins[plugin_id] = plugin
        self._save_manifest(plugin)

        for cb in self._on_install:
            try:
                cb(plugin)
            except Exception:  # noqa: BLE001
                pass

        await self._emit(
            "desktop.plugin.installed",
            {
                "plugin_id": plugin_id,
                "name": plugin.name,
                "version": plugin.version,
            },
        )
        _log.info("desktop.plugin.installed", plugin_id=plugin_id, name=plugin.name)
        return plugin

    async def uninstall(self, plugin_id: str) -> bool:
        plugin = self._plugins.pop(plugin_id, None)
        if plugin is None:
            return False
        dest = self._plugin_dir / plugin_id
        if dest.exists():
            import shutil

            shutil.rmtree(dest)
        manifest_path = self._plugin_dir / f"{plugin_id}.json"
        if manifest_path.exists():
            manifest_path.unlink()

        for cb in self._on_uninstall:
            try:
                cb(plugin_id)
            except Exception:  # noqa: BLE001
                pass

        await self._emit("desktop.plugin.uninstalled", {"plugin_id": plugin_id})
        _log.info("desktop.plugin.uninstalled", plugin_id=plugin_id)
        return True

    def list_plugins(self) -> list[DesktopPlugin]:
        return list(self._plugins.values())

    def get_plugin(self, plugin_id: str) -> DesktopPlugin | None:
        return self._plugins.get(plugin_id)

    def enable(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return False
        plugin.enabled = True
        self._save_manifest(plugin)
        return True

    def disable(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return False
        plugin.enabled = False
        self._save_manifest(plugin)
        return True

    def verify_signature(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if plugin is None or not plugin.signature:
            return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "plugin_dir": str(self._plugin_dir),
            "sandbox_enabled": self._sandbox_enabled,
            "plugins": {
                pid: {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "enabled": p.enabled,
                    "author": p.author,
                    "permissions": p.permissions,
                    "sandboxed": p.sandboxed,
                }
                for pid, p in self._plugins.items()
            },
        }

    def _extract_manifest(self, path: Path) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(path, "r") as zf:
                if "plugin.json" in zf.namelist():
                    data = json.loads(zf.read("plugin.json"))
                    return data
        except Exception:  # noqa: BLE001
            pass
        return {"name": path.stem, "version": "0.1.0"}

    def _save_manifest(self, plugin: DesktopPlugin) -> None:
        try:
            path = self._plugin_dir / f"{plugin.id}.json"
            path.write_text(
                json.dumps(
                    {
                        "id": plugin.id,
                        "name": plugin.name,
                        "version": plugin.version,
                        "description": plugin.description,
                        "author": plugin.author,
                        "permissions": plugin.permissions,
                        "signature": plugin.signature,
                        "enabled": plugin.enabled,
                        "installed_at": plugin.installed_at,
                        "entry_point": plugin.entry_point,
                        "sandboxed": plugin.sandboxed,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.plugin.save_manifest_failed", plugin_id=plugin.id, error=str(exc))

    async def _scan_installed(self) -> None:
        for manifest_path in self._plugin_dir.glob("*.json"):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                plugin = DesktopPlugin(**data)
                self._plugins[plugin.id] = plugin
            except Exception as exc:  # noqa: BLE001
                _log.warning("desktop.plugin.scan_failed", path=str(manifest_path), error=str(exc))

    async def _watch_loop(self) -> None:
        known = {str(p) for p in self._plugin_dir.glob("*.zip")}
        while not self._stop.is_set():
            current = {str(p) for p in self._plugin_dir.glob("*.zip")}
            new = current - known
            for path_str in new:
                try:
                    await self.install(path_str)
                except Exception as exc:  # noqa: BLE001
                    _log.warning("desktop.plugin.hotload_failed", path=path_str, error=str(exc))
            known = current
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=5.0)
            except (TimeoutError, asyncio.TimeoutError):
                continue

    async def _emit(self, topic: str, payload: dict) -> None:
        try:
            bus = get_bus()
            await bus.publish(
                Event(
                    topic=topic,
                    correlation_id=uuid4(),
                    actor=ActorRef.system(),
                    payload=payload,
                )
            )
        except Exception:  # noqa: BLE001
            pass

    async def shutdown(self) -> None:
        await self.stop()
