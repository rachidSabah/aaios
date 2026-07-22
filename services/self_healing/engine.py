"""Self-healing engine — automatically repairs detected system failures."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.gateway.audit import AuditEntry
from core.logging import get_logger
from services.doctor.manager import DoctorManager
from services.doctor.models import ScanType
from services.security.manager import get_security_manager
from services.self_healing.models import (
    HealingActionType,
    HealingStatus,
    HealingTrigger,
    RepairRecord,
)

_log = get_logger(__name__)

__all__ = ["SelfHealingEngine"]


class SelfHealingEngine:
    """Detects and repairs failures in AAiOS components."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        doctor_mgr: DoctorManager | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        self.doctor = doctor_mgr or DoctorManager(self.workspace_root)
        self.history_file = self.workspace_root / "diagnostics" / "self_healing_history.jsonl"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current

    async def run_healing(self, *, auto_approve: bool = False) -> list[RepairRecord]:
        """Scan system health and automatically repair detected issues."""
        report = self.doctor.run_scan(ScanType.FULL)
        records: list[RepairRecord] = []

        for issue in report.issues:
            if not issue.repair_available:
                continue

            trigger = self._map_issue_to_trigger(issue.id)
            if not trigger:
                continue

            action_type = self._map_trigger_to_action(trigger)
            record = RepairRecord(
                id=str(uuid4()),
                trigger=trigger,
                action_type=action_type,
                target=issue.id,
                status=HealingStatus.DETECTED,
                requires_approval=self._requires_user_approval(trigger),
                details=f"Detected via diagnostic issue {issue.id}: {issue.description}",
            )

            # Process repair
            if record.requires_approval and not auto_approve:
                record.status = HealingStatus.WAITING_APPROVAL
                _log.info("self_healing.waiting_approval", trigger=trigger.value)
                self._save_record(record)
                records.append(record)
                continue

            record.status = HealingStatus.IN_PROGRESS
            self._save_record(record)

            try:
                # Run the actual repair
                await self._execute_repair(record)
                record.status = HealingStatus.REPAIRED
                record.completed_at = datetime.now(UTC)
                _log.info("self_healing.repaired", trigger=trigger.value, action=action_type.value)
            except Exception as e:  # noqa: BLE001
                record.status = HealingStatus.FAILED
                record.error = str(e)
                record.completed_at = datetime.now(UTC)
                _log.error("self_healing.repair_failed", trigger=trigger.value, error=str(e))

            self._save_record(record)
            await self._audit_repair(record)
            records.append(record)

        return records

    async def approve_repair(self, record_id: str) -> bool:
        """Approve and execute a waiting repair action."""
        record = self.get_record(record_id)
        if not record or record.status != HealingStatus.WAITING_APPROVAL:
            return False

        record.approved = True
        record.status = HealingStatus.IN_PROGRESS
        record.started_at = datetime.now(UTC)
        self._save_record(record)

        try:
            await self._execute_repair(record)
            record.status = HealingStatus.REPAIRED
            record.completed_at = datetime.now(UTC)
        except Exception as e:  # noqa: BLE001
            record.status = HealingStatus.FAILED
            record.error = str(e)
            record.completed_at = datetime.now(UTC)

        self._save_record(record)
        await self._audit_repair(record)
        return record.status == HealingStatus.REPAIRED

    def get_record(self, record_id: str) -> RepairRecord | None:
        """Retrieve a specific repair record from history."""
        if not self.history_file.exists():
            return None
        with self.history_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("id") == record_id:
                    return RepairRecord(**data)
        return None

    def get_history(self) -> list[RepairRecord]:
        """Return the complete self-healing history (most recent first)."""
        history: list[RepairRecord] = []
        if not self.history_file.exists():
            return history
        with self.history_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                history.append(RepairRecord(**json.loads(line)))
        return list(reversed(history))

    # --- execution logic ----------------------------------------------

    async def _execute_repair(self, record: RepairRecord) -> None:
        """Dispatch the repair action based on trigger."""
        if record.trigger == HealingTrigger.MISSING_DEPENDENCY:
            self._repair_dependencies(record)
        elif record.trigger == HealingTrigger.BROKEN_CONFIGURATION:
            self._repair_configuration(record)
        elif record.trigger == HealingTrigger.DATABASE_CORRUPTION:
            self._repair_database_corruption(record)
        elif record.trigger == HealingTrigger.BROKEN_WORKSPACE:
            self._repair_workspace(record)
        elif record.trigger == HealingTrigger.PERMISSION_ISSUES:
            self._repair_permissions(record)
        elif record.trigger == HealingTrigger.CORRUPTED_CACHE:
            self._repair_cache(record)
        elif record.trigger == HealingTrigger.EXPIRED_CERTIFICATES:
            self._repair_certificates(record)
        elif record.trigger == HealingTrigger.BROKEN_AUDIT_CHAIN:
            self._repair_audit_chain(record)
        else:
            # Fallback or unhandled triggers escalate
            record.status = HealingStatus.ESCALATED
            raise NotImplementedError(
                f"Direct self-healing for {record.trigger} requires administrator escalation"
            )

    def _repair_dependencies(self, record: RepairRecord) -> None:
        """Repair missing dependencies by triggering reinstall."""
        record.details += "\nTriggering package reinstall..."
        venv_pip = self.workspace_root / ".venv" / "Scripts" / "pip.exe"
        if not venv_pip.exists():
            venv_pip = self.workspace_root / ".venv" / "bin" / "pip"

        if venv_pip.exists():
            subprocess.run([str(venv_pip), "install", "-e", ".[dev,windows]"], check=True)  # noqa: S603
        if (self.workspace_root / "package.json").exists():
            subprocess.run(["pnpm", "install"], check=True, shell=True)  # noqa: S602, S603, S607

    def _repair_configuration(self, record: RepairRecord) -> None:
        """Repair broken configuration by recreating config.yaml from defaults.yaml."""
        config_dir = self.workspace_root / "config"
        config_yaml = config_dir / "config.yaml"
        defaults_yaml = config_dir / "defaults.yaml"

        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)

        if config_yaml.exists():
            # Backup first, never silently delete user config
            backup = config_yaml.with_name(
                f"config.yaml.broken-{int(datetime.now(UTC).timestamp())}"
            )
            shutil.copy2(config_yaml, backup)
            record.backup_path = str(backup)
            record.details += f"\nBacked up broken config to {backup.name}"

        if defaults_yaml.exists():
            shutil.copy2(defaults_yaml, config_yaml)
            record.details += "\nRestored config.yaml from defaults.yaml"
        else:
            # Write a minimal defaults
            config_yaml.write_text("environment: development\nport: 8000\n", encoding="utf-8")
            record.details += "\nCreated minimal config.yaml"

    def _repair_database_corruption(self, record: RepairRecord) -> None:
        """Repair corrupted SQLite database file."""
        db_name = (
            record.target.replace("DB_CORRUPTED_", "")
            .replace("DB_CONN_FAILED_", "")
            .replace("DB_FILE_MISSING_", "")
            .lower()
        )
        db_path = self.workspace_root / "database" / f"{db_name}.db"

        # Backup the corrupted file
        if db_path.exists():
            backup = db_path.with_name(
                f"{db_name}.db.corrupted-{int(datetime.now(UTC).timestamp())}"
            )
            shutil.move(db_path, backup)
            record.backup_path = str(backup)
            record.details += f"\nMoved corrupted database to {backup.name}"

        # Re-bootstrap
        from services.installer.database import DatabaseBootstrapper
        from services.installer.workspace import WorkspaceBootstrapper

        ws = WorkspaceBootstrapper(self.workspace_root)
        db_boot = DatabaseBootstrapper(ws)
        db_boot._bootstrap_sqlite(db_name)  # noqa: SLF001
        record.details += f"\nRe-bootstrapped sqlite database: {db_name}"

    def _repair_workspace(self, record: RepairRecord) -> None:
        """Repair missing workspace directories."""
        from services.installer.workspace import WorkspaceBootstrapper

        ws = WorkspaceBootstrapper(self.workspace_root)
        ws.bootstrap()
        record.details += "\nRecreated missing workspace directories"

    def _repair_permissions(self, record: RepairRecord) -> None:
        """Repair directory permission configurations."""
        secrets_dir = self.workspace_root / "secrets"
        if secrets_dir.exists():
            if sys.platform != "win32":
                secrets_dir.chmod(0o700)
            record.details += "\nRestricted secrets folder permissions"

    def _repair_cache(self, record: RepairRecord) -> None:
        """Repair cache issues by purging cache directories."""
        cache_dir = self.workspace_root / "caches"
        tmp_dir = self.workspace_root / "tmp"
        for folder in (cache_dir, tmp_dir):
            if folder.exists():
                shutil.rmtree(folder)
                folder.mkdir(exist_ok=True)
        record.details += "\nPurged caches and temporary directories"

    def _repair_certificates(self, record: RepairRecord) -> None:
        """Repair expired/missing certificates by generating a self-signed cert."""
        cert_dir = self.workspace_root / "certificates"
        cert_dir.mkdir(parents=True, exist_ok=True)
        key_file = cert_dir / "localhost.key"
        cert_file = cert_dir / "localhost.crt"

        # Generate self-signed cert using openssl or python cryptography
        import datetime as dt

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AAiOS"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.now(dt.UTC))
            .not_valid_after(dt.datetime.now(dt.UTC) + dt.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        key_file.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        record.details += "\nGenerated new self-signed SSL certificate for localhost"

    def _repair_audit_chain(self, record: RepairRecord) -> None:
        """Repair audit log chain integrity."""
        audit_db = self.workspace_root / "database" / "audit.db"
        if audit_db.exists():
            backup = audit_db.with_name(f"audit.db.broken-{int(datetime.now(UTC).timestamp())}")
            shutil.move(audit_db, backup)
            record.backup_path = str(backup)

        from services.installer.database import DatabaseBootstrapper
        from services.installer.workspace import WorkspaceBootstrapper

        ws = WorkspaceBootstrapper(self.workspace_root)
        db_boot = DatabaseBootstrapper(ws)
        db_boot._bootstrap_sqlite("audit")  # noqa: SLF001
        record.details += "\nRe-initialized audit log database to restore chain integrity"

    # --- helper utilities ---------------------------------------------

    def _map_issue_to_trigger(self, issue_id: str) -> HealingTrigger | None:
        """Map a doctor issue ID to a self-healing trigger."""
        if (
            "CONFIG_DIR_MISSING" in issue_id
            or "DEFAULTS_YAML_MISSING" in issue_id
            or "CONFIG_YAML_MISSING" in issue_id
        ):
            return HealingTrigger.BROKEN_CONFIGURATION
        if "DB_DIR_MISSING" in issue_id:
            return HealingTrigger.BROKEN_WORKSPACE
        if "DB_FILE_MISSING_" in issue_id:
            return HealingTrigger.DATABASE_CORRUPTION
        if "DB_CORRUPTED_" in issue_id or "DB_CONN_FAILED_" in issue_id:
            return HealingTrigger.DATABASE_CORRUPTION
        if "PYTHON_DEP_MISSING_" in issue_id or "NODE_MODULES_MISSING" in issue_id:
            return HealingTrigger.MISSING_DEPENDENCY
        if "SECRETS_DIR_MISSING" in issue_id:
            return HealingTrigger.BROKEN_WORKSPACE
        if "SECRETS_DIR_PERMISSIONS_LOOSE" in issue_id:
            return HealingTrigger.PERMISSION_ISSUES
        if "CERTS_DIR_MISSING" in issue_id:
            return HealingTrigger.BROKEN_WORKSPACE
        if "AUDIT_CHAIN_VERIFY_FAILED" in issue_id:
            return HealingTrigger.BROKEN_AUDIT_CHAIN
        if "STORAGE_SPACE_WARNING" in issue_id:
            return HealingTrigger.CORRUPTED_CACHE
        if "AGENTS_DIR_MISSING" in issue_id or "PLUGINS_DIR_MISSING" in issue_id:
            return HealingTrigger.BROKEN_WORKSPACE
        if (
            "MISSION_TABLE_MISSING" in issue_id
            or "WORKFLOW_TABLE_MISSING" in issue_id
            or "KG_SCHEMA_INCOMPLETE" in issue_id
        ):
            return HealingTrigger.BROKEN_MIGRATIONS
        return None

    def _map_trigger_to_action(self, trigger: HealingTrigger) -> HealingActionType:
        """Determine default action type for a trigger."""
        if trigger in (HealingTrigger.MISSING_DEPENDENCY, HealingTrigger.BROKEN_WORKSPACE):
            return HealingActionType.REINSTALL
        if trigger == HealingTrigger.BROKEN_CONFIGURATION:
            return HealingActionType.RECONFIGURE
        if trigger in (HealingTrigger.DATABASE_CORRUPTION, HealingTrigger.BROKEN_AUDIT_CHAIN):
            return HealingActionType.RECOVER
        if trigger == HealingTrigger.PERMISSION_ISSUES:
            return HealingActionType.REPAIR
        if trigger == HealingTrigger.CORRUPTED_CACHE:
            return HealingActionType.INVALIDATE_CACHE
        if trigger == HealingTrigger.BROKEN_MIGRATIONS:
            return HealingActionType.REINDEX
        return HealingActionType.ESCALATE

    def _requires_user_approval(self, trigger: HealingTrigger) -> bool:
        """Check if the trigger requires user approval to proceed."""
        # Never silently change user configuration, database corruption recovery, or secret keys
        return trigger in (
            HealingTrigger.BROKEN_CONFIGURATION,
            HealingTrigger.DATABASE_CORRUPTION,
            HealingTrigger.INVALID_API_KEYS,
            HealingTrigger.EXPIRED_SECRETS,
        )

    def _save_record(self, record: RepairRecord) -> None:
        """Write the repair record to history."""
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), default=str) + "\n")

    async def _audit_repair(self, record: RepairRecord) -> None:
        """Log the self-healing action to the system audit log."""
        try:
            sec_mgr = get_security_manager()
            entry = AuditEntry(
                actor=ActorRef.system(),
                action="self_healing.repair",
                target=record.target,
                success=(record.status == HealingStatus.REPAIRED),
                reason=f"Self-healing {record.action_type.value} on {record.trigger.value}: {record.details}",
                correlation_id=record.id,
                metadata={"trigger": record.trigger.value, "backup_path": record.backup_path or ""},
            )
            await sec_mgr.log(entry)
            # Find the hash of the logged entry to associate it with the record
            latest_entries = await sec_mgr.get_audit_entries(limit=1)
            if latest_entries:
                record.audit_hash = latest_entries[0].hash
        except Exception:  # noqa: BLE001
            # Fallback if security manager isn't wired yet
            pass
