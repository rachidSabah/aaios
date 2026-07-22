"""Backup and Snapshot manager — manages backups, snapshots, and metadata exports."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sqlite3
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet

from core.logging import get_logger
from services.backup.models import BackupMetadata, BackupType, ExportFormat

_log = get_logger(__name__)

__all__ = ["BackupManager"]


class BackupManager:
    """Enterprise backup and snapshot management system."""

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        self.backup_dir = self.workspace_root / "backups"
        self.snapshot_dir = self.workspace_root / "snapshots"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Initialize encryption key or generate one
        self._key_file = self.workspace_root / "secrets" / "backup_key.key"
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._key_file.exists():
            self._key_file.write_bytes(Fernet.generate_key())
        self._fernet = Fernet(self._key_file.read_bytes())

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    def create_backup(  # noqa: PLR0912
        self,
        backup_type: BackupType = BackupType.FULL,
        format_type: ExportFormat = ExportFormat.ZIP,
        *,
        encrypt: bool = False,
        tags: list[str] | None = None,
        is_snapshot: bool = False,
    ) -> BackupMetadata:
        """Create a backup or snapshot of the workspace."""
        backup_id = str(uuid4())
        dest_dir = self.snapshot_dir if is_snapshot else self.backup_dir
        backup_path = dest_dir / f"backup-{backup_id}"
        backup_path.mkdir(parents=True, exist_ok=True)

        # Collect files to backup
        components = [
            "config",
            "database",
            "memory",
            "plugins",
            "providers",
            "secrets",
            "certificates",
            "dashboards",
            "reports",
        ]

        files_to_backup: list[Path] = []
        for comp in components:
            comp_path = self.workspace_root / comp
            if comp_path.exists():
                if comp_path.is_file():
                    files_to_backup.append(comp_path)
                else:
                    files_to_backup.extend([p for p in comp_path.rglob("*") if p.is_file()])

        # Apply Incremental/Differential logic
        last_full = self._get_latest_backup(BackupType.FULL, is_snapshot)
        last_backup = self._get_latest_backup(None, is_snapshot)

        if backup_type == BackupType.INCREMENTAL and last_backup:
            # Filter files modified since the last backup
            last_time = last_backup.timestamp.timestamp()
            files_to_backup = [f for f in files_to_backup if f.stat().st_mtime > last_time]
        elif backup_type == BackupType.DIFFERENTIAL and last_full:
            # Filter files modified since the last full backup
            full_time = last_full.timestamp.timestamp()
            files_to_backup = [f for f in files_to_backup if f.stat().st_mtime > full_time]

        # Copy files to temp backup path
        checksums: dict[str, str] = {}
        for file in files_to_backup:
            rel_path = file.relative_to(self.workspace_root)
            dest_file = backup_path / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest_file)
            # Compute sha256 checksum
            checksums[str(rel_path)] = self._compute_sha256(file)

        # Pack and compress
        archive_file = dest_dir / f"backup-{backup_id}.{format_type.value}"
        if format_type == ExportFormat.ZIP:
            self._zip_dir(backup_path, archive_file)
        elif format_type == ExportFormat.TAR:
            self._tar_dir(backup_path, archive_file)
        else:
            # For JSON/YAML, copy files as is or compile to metadata
            shutil.rmtree(backup_path)
            backup_path.mkdir(parents=True, exist_ok=True)
            # Write a single JSON representation of files
            backup_dict: dict[str, str] = {}
            for file in files_to_backup:
                rel_path = file.relative_to(self.workspace_root)
                backup_dict[str(rel_path)] = file.read_text(encoding="utf-8", errors="ignore")
            if format_type == ExportFormat.JSON:
                archive_file = dest_dir / f"backup-{backup_id}.json"
                archive_file.write_text(json.dumps(backup_dict, indent=2))
            else:
                archive_file = dest_dir / f"backup-{backup_id}.yaml"
                import yaml

                archive_file.write_text(yaml.dump(backup_dict))

        # Encrypt if requested
        if encrypt:
            data = archive_file.read_bytes()
            encrypted_data = self._fernet.encrypt(data)
            archive_file.write_bytes(encrypted_data)

        # Clean up temp folder
        shutil.rmtree(backup_path)

        # Generate metadata
        git_commit = self._get_git_commit()
        database_versions = self._get_db_versions()
        metadata = BackupMetadata(
            id=backup_id,
            timestamp=datetime.now(UTC),
            backup_type=backup_type,
            format=format_type,
            version="5.3.2",
            git_commit=git_commit,
            database_versions=database_versions,
            platform_info={
                "system": platform.system(),
                "node": platform.node(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            checksums=checksums,
            size_bytes=archive_file.stat().st_size,
            tags=tags or [],
            encrypted=encrypt,
        )

        # Write metadata file
        meta_file = dest_dir / f"backup-{backup_id}.meta.json"
        meta_file.write_text(metadata.model_dump_json(indent=2))

        _log.info(
            "backup.created",
            backup_id=backup_id,
            type=backup_type.value,
            size=metadata.size_bytes,
        )
        return metadata

    def list_backups(self, *, is_snapshot: bool = False) -> list[BackupMetadata]:
        """List all available backups or snapshots."""
        dest_dir = self.snapshot_dir if is_snapshot else self.backup_dir
        results: list[BackupMetadata] = []
        for file in dest_dir.glob("*.meta.json"):
            try:
                results.append(BackupMetadata.model_validate_json(file.read_text(encoding="utf-8")))
            except Exception as e:  # noqa: BLE001
                _log.warning("backup.metadata_parse_failed", path=str(file), error=str(e))
        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def get_backup(self, backup_id: str, *, is_snapshot: bool = False) -> BackupMetadata | None:
        """Get metadata for a specific backup or snapshot."""
        dest_dir = self.snapshot_dir if is_snapshot else self.backup_dir
        meta_file = dest_dir / f"backup-{backup_id}.meta.json"
        if not meta_file.exists():
            return None
        try:
            return BackupMetadata.model_validate_json(meta_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def delete_backup(self, backup_id: str, *, is_snapshot: bool = False) -> bool:
        """Delete a backup or snapshot and its metadata."""
        dest_dir = self.snapshot_dir if is_snapshot else self.backup_dir
        meta_file = dest_dir / f"backup-{backup_id}.meta.json"
        if not meta_file.exists():
            return False

        try:
            metadata = BackupMetadata.model_validate_json(meta_file.read_text(encoding="utf-8"))
            archive_file = dest_dir / f"backup-{backup_id}.{metadata.format.value}"
            if archive_file.exists():
                archive_file.unlink()
            meta_file.unlink()
            _log.info("backup.deleted", backup_id=backup_id)
            return True
        except Exception as e:  # noqa: BLE001
            _log.error("backup.delete_failed", backup_id=backup_id, error=str(e))
            return False

    def compare_snapshots(self, snap_id_a: str, snap_id_b: str) -> dict[str, Any]:
        """Compare two snapshots and return file and metadata differences."""
        meta_a = self.get_backup(snap_id_a, is_snapshot=True)
        meta_b = self.get_backup(snap_id_b, is_snapshot=True)
        if not meta_a or not meta_b:
            raise FileNotFoundError("One or both snapshots do not exist")

        files_a = set(meta_a.checksums.keys())
        files_b = set(meta_b.checksums.keys())

        added = list(files_b - files_a)
        deleted = list(files_a - files_b)
        modified: list[str] = []

        for common in files_a & files_b:
            if meta_a.checksums[common] != meta_b.checksums[common]:
                modified.append(common)

        return {
            "snapshot_a": snap_id_a,
            "snapshot_b": snap_id_b,
            "added": added,
            "deleted": deleted,
            "modified": modified,
            "metadata_diff": {
                "version_diff": (meta_a.version, meta_b.version),
                "commit_diff": (meta_a.git_commit, meta_b.git_commit),
                "db_version_diff": (meta_a.database_versions, meta_b.database_versions),
            },
        }

    def export_backup(self, backup_id: str, dest_path: Path, *, is_snapshot: bool = False) -> Path:
        """Export a backup archive and metadata to a target location (cloud or local disk)."""
        dest_dir = self.snapshot_dir if is_snapshot else self.backup_dir
        meta_file = dest_dir / f"backup-{backup_id}.meta.json"
        if not meta_file.exists():
            raise FileNotFoundError(f"Backup {backup_id} not found")

        metadata = BackupMetadata.model_validate_json(meta_file.read_text(encoding="utf-8"))
        archive_file = dest_dir / f"backup-{backup_id}.{metadata.format.value}"

        dest_path.mkdir(parents=True, exist_ok=True)
        shutil.copy2(meta_file, dest_path / meta_file.name)
        shutil.copy2(archive_file, dest_path / archive_file.name)

        return dest_path / archive_file.name

    def import_backup(self, src_archive_path: Path, *, is_snapshot: bool = False) -> BackupMetadata:
        """Import a backup or snapshot into the system."""
        if not src_archive_path.exists():
            raise FileNotFoundError(f"Source archive {src_archive_path} does not exist")

        dest_dir = self.snapshot_dir if is_snapshot else self.backup_dir

        # Look for corresponding metadata
        meta_name = src_archive_path.name.split(".")[0] + ".meta.json"
        src_meta_path = src_archive_path.parent / meta_name

        if not src_meta_path.exists():
            raise FileNotFoundError(f"Associated metadata file {src_meta_path} was not found")

        # Verify metadata
        metadata = BackupMetadata.model_validate_json(src_meta_path.read_text(encoding="utf-8"))

        # Copy to destination
        shutil.copy2(src_meta_path, dest_dir / meta_name)
        shutil.copy2(src_archive_path, dest_dir / src_archive_path.name)

        _log.info("backup.imported", backup_id=metadata.id)
        return metadata

    # --- helper utilities ---------------------------------------------

    def _compute_sha256(self, path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _get_latest_backup(
        self, type_filter: BackupType | None = None, is_snapshot: bool = False
    ) -> BackupMetadata | None:
        """Get the latest backup, optionally filtered by type."""
        backups = self.list_backups(is_snapshot=is_snapshot)
        if type_filter:
            backups = [b for b in backups if b.backup_type == type_filter]
        return backups[0] if backups else None

    def _get_git_commit(self) -> str | None:
        """Get current git commit hash if in a repository."""
        try:
            import subprocess

            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],  # noqa: S603, S607
                capture_output=True,
                text=True,
                cwd=str(self.workspace_root),
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:  # noqa: BLE001
            pass
        return None

    def _get_db_versions(self) -> dict[str, int]:
        """Get schema versions from SQLite database files."""
        versions: dict[str, int] = {}
        db_dir = self.workspace_root / "database"
        if not db_dir.exists():
            return versions

        for db_file in db_dir.glob("*.db"):
            db_name = db_file.stem
            try:
                conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT max(id) FROM schema_migrations WHERE status='applied';")
                    row = cursor.fetchone()
                    versions[db_name] = int(row[0]) if row and row[0] is not None else 0
                except sqlite3.Error:
                    # fallback to user_version pragma
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA user_version;")
                    row = cursor.fetchone()
                    versions[db_name] = row[0] if row else 0
                finally:
                    conn.close()
            except sqlite3.Error:
                versions[db_name] = 0
        return versions

    def _zip_dir(self, src: Path, dest: Path) -> None:
        """Compress directory into zip file."""
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(src):
                for file in files:
                    file_path = Path(root) / file
                    zipf.write(file_path, file_path.relative_to(src))

    def _tar_dir(self, src: Path, dest: Path) -> None:
        """Compress directory into gzipped tar file."""
        with tarfile.open(dest, "w:gz") as tar:
            tar.add(src, arcname=".")
