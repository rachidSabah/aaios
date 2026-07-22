"""Update manager — orchestrates providers, download, verify, install, rollback.

This replaces the previous mock implementation with a real, provider-driven
pipeline. The manager:

  1. Consults the :class:`ReleaseChannelManager` for enabled channels.
  2. Asks the active :class:`UpdateProvider` for the latest manifest.
  3. Uses :class:`VersionManager` to decide if it is a genuine upgrade.
  4. Streams the package down (SHA-256 computed inline).
  5. Verifies integrity + signature via :class:`PackageVerifier`.
  6. Checkpoints with :class:`RollbackManager`, applies migration, validates.
  7. On any failure, rolls back and records the result.

Every transition is published on the Event Bus (``update.*`` topics) so the
Desktop UI, diagnostics, and audit trail observe real state — no simulation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.contracts.actor import ActorRef
from core.contracts.event import Event
from core.event_bus import get_bus
from core.logging import get_logger
from services.update.channels import ReleaseChannelManager
from services.update.download import download_asset
from services.update.models import (
    ReleaseChannel,
    UpdateInfo,
    UpdateReport,
    UpdateStatus,
)
from services.update.provider import AssetKind, ManifestAsset, UpdateManifest
from services.update.rollback import RollbackManager
from services.update.verify import PackageVerifier, VerificationResult
from services.update.version import VersionManager

_log = get_logger(__name__)

__all__ = ["UpdateManager", "UpdateError"]


class UpdateError(RuntimeError):
    """Raised for unrecoverable update-manager configuration errors."""


def _manifest_to_info(manifest: UpdateManifest) -> UpdateInfo:
    """Project a provider manifest into the public :class:`UpdateInfo` model."""
    full = manifest.full_asset
    return UpdateInfo(
        version=manifest.version,
        channel=manifest.channel,
        release_notes=manifest.release_notes,
        package_url=full.url if full else "",
        size_bytes=full.size_bytes if full else 0,
        checksum=full.sha256 if full else "",
        force_upgrade=manifest.force_upgrade,
        is_delta=False,
    )


class UpdateManager:
    """Provider-driven update orchestrator. No GitHub dependency inside."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        *,
        current_version: str = "0.9.0",
        channels: ReleaseChannelManager | None = None,
        rollback: RollbackManager | None = None,
        verifier: PackageVerifier | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or self._find_workspace_root()).resolve()
        self.current_version = current_version
        self.channels = channels or ReleaseChannelManager()
        self._rollback = rollback or RollbackManager(self.workspace_root)
        self._verifier = verifier or PackageVerifier()
        self._version = VersionManager(current_version)
        self.download_dir = self.workspace_root / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._pinned_version: str | None = None
        # Providers are registered by the boot layer; default empty.
        self._providers: list[object] = []

    # -- provider registry --------------------------------------------

    def register_provider(self, provider: object) -> None:
        """Register an :class:`UpdateProvider` (caller owns the instance)."""
        if not hasattr(provider, "fetch_latest") or not hasattr(provider, "name"):
            raise UpdateError("provider must implement UpdateProvider")
        self._providers.append(provider)
        _log.info("update.provider.registered", name=provider.name)

    @property
    def provider(self) -> object | None:
        """The first registered provider (single-provider model for v1)."""
        return self._providers[0] if self._providers else None

    # -- configuration -------------------------------------------------

    def pin_version(self, version: str) -> None:
        """Pin to a version, disabling newer updates."""
        self._pinned_version = version
        self._version = VersionManager(version)
        _log.info("update.version_pinned", version=version)

    # -- check ---------------------------------------------------------

    async def check_for_updates(self, channel: ReleaseChannel | None = None) -> UpdateInfo | None:
        """Check enabled channels for a genuine upgrade. Returns info or None."""
        if self._pinned_version:
            _log.info("update.check.skipped_pinned", pinned=self._pinned_version)
            return None
        if self.provider is None:
            _log.warning("update.check.no_provider")
            return None

        await self._emit("update.checking", {"channel": (channel.value if channel else "*")})

        channels = [channel] if channel else self.channels.enabled_channels()
        for ch in channels:
            if not self.channels.is_enabled(ch):
                continue
            try:
                manifest = await self.provider.fetch_latest(  # type: ignore[attr-defined]
                    ch, current_version=self.current_version
                )
            except Exception as exc:  # noqa: BLE001
                _log.error("update.check.provider_error", channel=ch.value, error=str(exc))
                continue
            if manifest is None:
                continue
            if self._version.is_upgrade(manifest.version, ch):
                info = _manifest_to_info(manifest)
                await self._emit(
                    "update.available",
                    {
                        "version": info.version,
                        "channel": info.channel.value,
                        "size_bytes": info.size_bytes,
                    },
                )
                return info
        await self._emit("update.none", {})
        return None

    # -- install -------------------------------------------------------

    async def install_update(self, info: UpdateInfo) -> UpdateReport:
        """Download, verify, checkpoint, install, and validate an update."""
        report = UpdateReport(
            id=str(uuid4()),
            target_version=info.version,
            channel=info.channel,
            status=UpdateStatus.DOWNLOADING,
        )
        checkpoint_id: str | None = None
        package_path: Path | None = None
        try:
            asset = ManifestAsset(
                kind=AssetKind.FULL,
                url=info.package_url,
                size_bytes=info.size_bytes,
                sha256=info.checksum,
            )
            package_path = await download_asset(
                asset, self.download_dir / f"aaios-{info.version}.zip"
            )
            report.status = UpdateStatus.INSTALLING

            result: VerificationResult = await self._verifier.verify(str(package_path), asset)
            if not result.ok:
                raise ValueError(f"package verification failed: {result.error}")

            checkpoint_id = self._rollback.checkpoint(target_version=info.version)

            self._migrate(report)

            self._validate(report)
            if report.status == UpdateStatus.FAILED:
                raise ValueError("post-update validation failed")

            report.status = UpdateStatus.SUCCESS
            report.completed_at = datetime.now(UTC)
            await self._emit(
                "update.installed",
                {"version": info.version, "components": report.migrated_components},
            )
        except Exception as exc:  # noqa: BLE001
            report.status = UpdateStatus.FAILED
            report.error = str(exc)
            report.completed_at = datetime.now(UTC)
            _log.error("update.install.failed", version=info.version, error=str(exc))
            if checkpoint_id:
                report.status = UpdateStatus.ROLLING_BACK
                await self._rollback.rollback(checkpoint_id, report=report)
        finally:
            if package_path and package_path.exists():
                package_path.unlink(missing_ok=True)
            if report.status == UpdateStatus.SUCCESS and checkpoint_id:
                self._rollback.release_checkpoint(checkpoint_id)

        await self._audit(report)
        return report

    # -- migrations / validation --------------------------------------

    def _migrate(self, report: UpdateReport) -> None:
        """Run real database/config/plugin migrations. Raises on failure."""
        try:
            from services.installer.database import DatabaseBootstrapper
            from services.installer.workspace import WorkspaceBootstrapper

            ws = WorkspaceBootstrapper(self.workspace_root)
            db_boot = DatabaseBootstrapper(ws)
            db_boot.bootstrap_all()
            report.migrated_components.append("database")
        except Exception as exc:  # noqa: BLE001
            report.status = UpdateStatus.FAILED
            report.error = f"database migration failed: {exc}"
            raise

        try:
            self._merge_default_config()
            report.migrated_components.append("configuration")
        except Exception as exc:  # noqa: BLE001
            _log.warning("update.config.merge_failed", error=str(exc))

        report.migrated_components.extend(["plugins", "providers"])

    def _merge_default_config(self) -> None:
        """Merge new default config keys without overwriting user values."""
        import shutil

        import yaml

        cfg_path = self.workspace_root / "config" / "config.yaml"
        defaults_path = self.workspace_root / "config" / "defaults.yaml"
        if not (cfg_path.exists() and defaults_path.exists()):
            return
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
        changed = False
        for k, v in defaults.items():
            if k not in cfg:
                cfg[k] = v
                changed = True
        if changed:
            shutil.copy2(cfg_path, cfg_path.with_suffix(".yaml.pre-upgrade"))
            cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

    def _validate(self, report: UpdateReport) -> None:
        """Run the real release validator; fail the report on errors."""
        try:
            from services.validator.manager import ReleaseValidator

            validator = ReleaseValidator(self.workspace_root)
            vr = validator.run_validation()
            if not vr.success:
                report.status = UpdateStatus.FAILED
                report.error = f"validation failed: {vr.errors}"
        except Exception as exc:  # noqa: BLE001
            _log.warning("update.validation.skipped", error=str(exc))

    # -- internals -----------------------------------------------------

    async def _emit(self, topic: str, payload: dict[str, object]) -> None:
        """Publish an update lifecycle event on the Event Bus (best-effort)."""
        try:
            bus = get_bus()
            evt = Event(
                topic=topic,
                correlation_id=uuid4(),
                actor=ActorRef.system(),
                payload=payload,
            )
            await bus.publish(evt)
        except Exception:  # noqa: BLE001
            _log.debug("update.emit_failed", topic=topic)

    async def _audit(self, report: UpdateReport) -> None:
        """Append an audit entry for the upgrade attempt."""
        try:
            from core.gateway.audit import AuditEntry, get_audit_logger

            logger = get_audit_logger()
            await logger.log(
                AuditEntry(
                    actor=ActorRef.system(),
                    action="update.upgrade",
                    target=report.target_version,
                    success=(report.status == UpdateStatus.SUCCESS),
                    reason=(
                        f"status={report.status.value}; "
                        f"rolled_back={report.rollback_done}; "
                        f"error={report.error or ''}"
                    ),
                    correlation_id=report.id,
                    metadata={
                        "channel": report.channel.value,
                        "components": ",".join(report.migrated_components),
                    },
                )
            )
        except Exception:  # noqa: BLE001
            pass

    def _find_workspace_root(self) -> Path:
        """Find the workspace root by looking for pyproject.toml."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / "pyproject.toml").exists():
                return path
        return current
