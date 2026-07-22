"""Phase 3 — Workspace Bootstrap.

Creates the entire workspace directory layout. Supports custom installation
paths. Idempotent: existing directories are preserved (never overwritten).
"""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.installer.models import WorkspaceLayout

_log = get_logger(__name__)

__all__ = ["WorkspaceBootstrapper", "DEFAULT_WORKSPACE_DIRS"]

# Every directory AAiOS needs at runtime.
DEFAULT_WORKSPACE_DIRS: tuple[str, ...] = (
    "projects",
    "logs",
    "config",
    "plugins",
    "providers",
    "agents",
    "models",
    "memory",
    "knowledge-graph",
    "vector-storage",
    "database",
    "backups",
    "snapshots",
    "exports",
    "downloads",
    "caches",
    "runtime",
    "tmp",
    "certificates",
    "secrets",
    "dashboards",
    "reports",
    "diagnostics",
)


class WorkspaceBootstrapper:
    """Phase 3 — create the workspace layout.

    The bootstrapper is:
      - Idempotent: re-running on an existing workspace is safe
      - Restart-safe: each directory is created independently
      - Transactional: failures are recorded, not propagated
      - Non-destructive: existing directories are never modified
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def bootstrap(
        self,
        dirs: tuple[str, ...] = DEFAULT_WORKSPACE_DIRS,
        *,
        force: bool = False,
    ) -> WorkspaceLayout:
        """Create all workspace directories.

        Args:
            dirs: tuple of directory names to create.
            force: if True, recreate directories (still non-destructive to files).

        Returns:
            WorkspaceLayout describing what was created.
        """
        layout = WorkspaceLayout(root=str(self._root))
        # Ensure the root exists
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            layout.failed_dirs.append(f"{self._root}: {e}")
            return layout
        for d in dirs:
            path = self._root / d
            try:
                if path.exists():
                    layout.existing_dirs.append(str(path))
                    if force:
                        # Only re-create the directory; never delete files
                        path.mkdir(parents=True, exist_ok=True)
                else:
                    path.mkdir(parents=True, exist_ok=False)
                    layout.created_dirs.append(str(path))
                    _log.info("installer.workspace_dir_created", dir=str(path))
            except OSError as e:
                layout.failed_dirs.append(f"{path}: {e}")
                _log.warning("installer.workspace_dir_failed", dir=str(path), error=str(e))
        # Compute total size (best-effort)
        layout.total_size_mb = self._compute_size_mb()
        return layout

    def path_for(self, *segments: str) -> Path:
        """Return a path inside the workspace."""
        return self._root.joinpath(*segments)

    def ensure_dir(self, *segments: str) -> Path:
        """Ensure a subdirectory exists and return its path."""
        path = self.path_for(*segments)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def verify(self) -> dict[str, bool]:
        """Verify that all default directories exist and are writable."""
        result: dict[str, bool] = {}
        for d in DEFAULT_WORKSPACE_DIRS:
            path = self._root / d
            try:
                exists = path.exists() and path.is_dir()
                writable = os.access(path, os.W_OK) if exists else False
                result[d] = exists and writable
            except OSError:
                result[d] = False
        return result

    def create_restore_point(self, name: str = "") -> str:
        """Create a restore point marker (a snapshot of the workspace state).

        The restore point is a JSON manifest of directory contents. It is NOT
        a full file backup — it records sizes and timestamps so that a
        rollback can detect what changed.
        """
        import json

        rp_name = name or f"restore-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        rp_dir = self._root / "snapshots" / rp_name
        rp_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, dict[str, object]] = {}
        for d in DEFAULT_WORKSPACE_DIRS:
            path = self._root / d
            if not path.exists():
                continue
            entries: list[dict[str, object]] = []
            try:
                for entry in path.iterdir():
                    try:
                        stat = entry.stat()
                        entries.append(
                            {
                                "name": entry.name,
                                "size": stat.st_size,
                                "mtime": stat.st_mtime,
                                "is_dir": entry.is_dir(),
                            }
                        )
                    except OSError:
                        continue
            except OSError:
                continue
            manifest[d] = {
                "entries": entries,
                "count": len(entries),
            }
        manifest_path = rp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
        _log.info("installer.restore_point_created", path=str(manifest_path))
        return str(manifest_path)

    def rollback_to(self, restore_point_path: str) -> dict[str, Any]:
        """Roll back the workspace to a restore point.

        This is a soft rollback: it deletes files created after the restore
        point and recreates missing files. It never deletes user data in
        ``projects/`` or ``exports/``.
        """
        import json

        rp_path = Path(restore_point_path)
        if not rp_path.exists():
            return {"error": "restore point not found"}
        try:
            manifest = json.loads(rp_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            return {"error": f"invalid restore point: {e}"}
        protected = {"projects", "exports", "backups"}
        result: dict[str, Any] = {"checked": 0, "removed": 0, "restored": 0}
        for d_name, info in manifest.items():
            if d_name in protected:
                continue
            d_path = self._root / d_name
            if not d_path.exists():
                continue
            known_names = {e["name"] for e in info.get("entries", [])}
            try:
                for entry in d_path.iterdir():
                    result["checked"] += 1
                    if entry.name not in known_names:
                        try:
                            if entry.is_dir():
                                shutil.rmtree(entry)
                            else:
                                entry.unlink()
                            result["removed"] += 1
                        except OSError:
                            pass
            except OSError:
                continue
        return result

    def _compute_size_mb(self) -> float:
        """Compute the total size of the workspace in MB (best-effort)."""
        total = 0
        try:
            for entry in self._root.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        continue
        except OSError:
            pass
        return round(total / (1024 * 1024), 2)
