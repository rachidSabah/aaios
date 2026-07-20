"""GitHub Releases update provider — the first concrete :class:`UpdateProvider`.

This is a *real* implementation: it queries the GitHub REST API for releases,
maps them to :class:`~services.update.provider.UpdateManifest`, and never
hard-codes fake versions. It degrades cleanly when offline (returns ``None`` so
the framework can fall back to cached metadata), and honours the Desktop
Runtime's rule that nothing else in the system imports GitHub directly.

The release-tag → channel mapping is explicit and configurable:
  - ``vX.Y.Z`` stable tags          -> STABLE
  - ``vX.Y.Z-lts`` tags             -> LTS
  - ``vX.Y.Z-beta*`` / ``-rc*``     -> BETA
  - ``vX.Y.Z-nightly*``             -> NIGHTLY
  - ``vX.Y.Z-enterprise*``          -> ENTERPRISE

All network access goes through ``httpx.AsyncClient`` so it is fully mockable
in tests via dependency injection (the client is a constructor parameter).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from core.logging import get_logger
from services.update.models import ReleaseChannel
from services.update.provider import (
    AssetKind,
    ManifestAsset,
    UpdateManifest,
    UpdateProvider,
)

_log = get_logger(__name__)

_API_ROOT = "https://api.github.com"
_DEFAULT_ACCEPT = "application/vnd.github+json"


def _channel_for_tag(tag: str) -> ReleaseChannel:
    """Map a git tag to a release channel by convention."""
    t = tag.lower()
    if t.endswith("-lts"):
        return ReleaseChannel.LTS
    if "enterprise" in t:
        return ReleaseChannel.ENTERPRISE
    if "nightly" in t:
        return ReleaseChannel.NIGHTLY
    if "beta" in t or "rc" in t:
        return ReleaseChannel.BETA
    return ReleaseChannel.STABLE


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _asset_kind(name: str) -> AssetKind:
    low = name.lower()
    if low.endswith((".sig", ".asc", ".sha256.sig")):
        return AssetKind.SIGNATURE
    if "delta" in low:
        return AssetKind.DELTA
    if "manifest" in low:
        return AssetKind.MANIFEST
    return AssetKind.FULL


class GitHubReleaseProvider(UpdateProvider):
    """Fetch update manifests from a GitHub repository's published releases."""

    def __init__(
        self,
        repo: str = "rachidSabah/aaios",
        *,
        client: httpx.AsyncClient | None = None,
        token: str | None = None,
        api_root: str = _API_ROOT,
    ) -> None:
        self.repo = repo
        self._client = client  # injected in tests; created lazily otherwise
        self._token = token
        self._api_root = api_root.rstrip("/")

    @property
    def name(self) -> str:
        return f"github-releases:{self.repo}"

    # -- public API ----------------------------------------------------

    async def fetch_latest(
        self,
        channel: ReleaseChannel,
        *,
        current_version: str,
        timeout_s: float = 10.0,
    ) -> UpdateManifest | None:
        client = self._client or httpx.AsyncClient(
            timeout=timeout_s, headers=self._headers()
        )
        own_client = self._client is None
        try:
            url = f"{self._api_root}/repos/{self.repo}/releases"
            resp = await client.get(url)
            if resp.status_code == 404:
                _log.warning("update.github.repo_not_found", repo=self.repo)
                return None
            resp.raise_for_status()
            releases: list[dict[str, Any]] = resp.json()
        except httpx.HTTPError as exc:  # network/offline -> graceful
            _log.info("update.github.unreachable", repo=self.repo, error=str(exc))
            return None
        finally:
            if own_client:
                await client.aclose()

        candidates = [
            r
            for r in releases
            if not r.get("draft")
            and _channel_for_tag(r.get("tag_name", "")) == channel
        ]
        if not candidates:
            return None
        # Newest published first.
        candidates.sort(
            key=lambda r: _parse_published(r.get("published_at")) or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        latest = candidates[0]
        return self._to_manifest(latest)

    # -- helpers -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": _DEFAULT_ACCEPT, "User-Agent": "AAiOS-UpdateClient"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _to_manifest(self, release: dict[str, Any]) -> UpdateManifest:
        tag = release.get("tag_name", "")
        assets: list[ManifestAsset] = []
        for a in release.get("assets", []):
            name = a.get("name", "")
            assets.append(
                ManifestAsset(
                    kind=_asset_kind(name),
                    url=a.get("browser_download_url", ""),
                    size_bytes=int(a.get("size", 0)),
                    sha256="",  # GitHub does not publish checksums; see verify.py note
                    signature="",
                )
            )
        return UpdateManifest(
            version=tag.lstrip("v"),
            channel=_channel_for_tag(tag),
            release_notes=(release.get("body") or "").strip(),
            published_at=_parse_published(release.get("published_at")),
            prerelease=bool(release.get("prerelease")),
            draft=bool(release.get("draft")),
            assets=assets,
            force_upgrade=False,
        )

    @staticmethod
    def tag_for(version: str, channel: ReleaseChannel) -> str:
        """Build the git tag that a channel uses for a given version.

        Inverse of :func:`_channel_for_tag`; used by the manifest generator and
        release tooling so channel + version round-trip consistently.
        """
        if channel == ReleaseChannel.LTS:
            return f"v{version}-lts"
        if channel == ReleaseChannel.ENTERPRISE:
            return f"v{version}-enterprise"
        if channel == ReleaseChannel.NIGHTLY:
            return f"v{version}-nightly"
        if channel == ReleaseChannel.BETA:
            return f"v{version}-beta"
        return f"v{version}"
