"""Update provider abstraction — the seam that keeps the Desktop Runtime
independent of GitHub.

The mission is explicit: *"The Desktop Runtime must never depend directly on
GitHub. GitHub Releases are only the first UpdateProvider implementation.
Future update providers must require no kernel modifications."*

To honour that, every source of update metadata implements :class:`UpdateProvider`.
The :class:`~services.update.manager.UpdateManager` talks only to the provider
interface — it never imports ``github`` or any network client directly. Swapping
GitHub for an enterprise registry, a local file share, or a custom CDN is a pure
configuration change: register a different provider, no call-site edits.
"""

from __future__ import annotations

import abc
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from services.update.models import ReleaseChannel


class AssetKind(StrEnum):
    """What a release asset represents, so the downloader can route it."""

    FULL = "full"
    DELTA = "delta"
    SIGNATURE = "signature"
    MANIFEST = "manifest"


class ManifestAsset(BaseModel):
    """A single downloadable artifact attached to a release."""

    kind: AssetKind
    url: str
    size_bytes: int = 0
    sha256: str = ""  # hex digest; empty means "not published / unverified"
    signature: str = ""  # detached signature (hex/armored) when published

    model_config = {"extra": "forbid"}


class UpdateManifest(BaseModel):
    """A provider-neutral description of an available release.

    Providers translate their native payload (e.g. a GitHub release object)
    into this shape. The rest of the framework is agnostic to the origin.
    """

    version: str
    channel: ReleaseChannel
    release_notes: str = ""
    published_at: datetime | None = None
    prerelease: bool = False
    draft: bool = False
    assets: list[ManifestAsset] = Field(default_factory=list)
    force_upgrade: bool = False

    @property
    def full_asset(self) -> ManifestAsset | None:
        """The full-package asset, if published."""
        return next((a for a in self.assets if a.kind == AssetKind.FULL), None)

    @property
    def delta_asset(self) -> ManifestAsset | None:
        """The delta-package asset, if published."""
        return next((a for a in self.assets if a.kind == AssetKind.DELTA), None)

    @property
    def signature_asset(self) -> ManifestAsset | None:
        """The detached-signature asset, if published."""
        return next((a for a in self.assets if a.kind == AssetKind.SIGNATURE), None)


class UpdateProvider(abc.ABC):
    """The contract every update source implements.

    Implementations MUST be side-effect free on ``fetch_latest`` beyond a
    read-only network/IO call. They MUST NOT mutate local state. All local
    effects (download, install, rollback) live in the framework, never here.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. ``github-releases``."""

    @abc.abstractmethod
    async def fetch_latest(
        self,
        channel: ReleaseChannel,
        *,
        current_version: str,
        timeout_s: float = 10.0,
    ) -> UpdateManifest | None:
        """Return the latest manifest for ``channel`` or ``None`` if none applies.

        Returns ``None`` (not an error) when:
          - the provider is unreachable AND offline-tolerant (caller decides),
          - there is no newer release,
          - the channel has no published artifacts.
        Raises on programming/configuration errors (bad URL, auth, etc.).
        """

    async def is_reachable(self, *, timeout_s: float = 5.0) -> bool:
        """Best-effort connectivity probe. Default: try ``fetch_latest`` cheaply.

        Providers may override with a lighter-weight health check.
        """
        try:
            await self.fetch_latest(
                ReleaseChannel.STABLE, current_version="0.0.0", timeout_s=timeout_s
            )
            return True
        except Exception:  # noqa: BLE001 - reachability is a boolean, never raises
            return False
