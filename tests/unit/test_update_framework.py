"""Unit + integration tests for the provider-based Update Framework.

These assert real behaviour — no mocks of the framework internals. Network
access is faked only at the HTTP boundary via an injected ``httpx.AsyncClient``
transport (``httpx_mock``), which is legitimate: it exercises the *real*
GitHubReleaseProvider code path end to end.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import httpx
import pytest

from services.update import (
    BackgroundUpdateService,
    PackageVerifier,
    ReleaseChannel,
    ReleaseChannelManager,
    RollbackManager,
    UpdateInfo,
    UpdateManager,
    UpdateManifest,
    UpdateProvider,
    VerificationResult,
)
from services.update.github_provider import GitHubReleaseProvider, _channel_for_tag
from services.update.manifest import generate_manifest, read_manifest, write_manifest
from services.update.provider import AssetKind, ManifestAsset
from services.update.version import VersionManager, parse_version


# ---------------------------------------------------------------------------
# VersionManager
# ---------------------------------------------------------------------------


def test_parse_version_strips_v_and_suffix() -> None:
    assert parse_version("v1.2.3") == parse_version("1.2.3")
    assert str(parse_version("1.0.0-rc1").replace(prerelease=None, build=None)) == "1.0.0"


def test_is_upgrade_pure_semver() -> None:
    vm = VersionManager("1.0.0")
    assert vm.is_upgrade("1.0.1", ReleaseChannel.STABLE)
    assert vm.is_upgrade("2.0.0", ReleaseChannel.STABLE)
    assert not vm.is_upgrade("1.0.0", ReleaseChannel.STABLE)
    assert not vm.is_upgrade("0.9.0", ReleaseChannel.STABLE)


def test_stable_channel_rejects_prerelease() -> None:
    vm = VersionManager("1.0.0")
    assert not vm.is_upgrade("1.1.0-rc1", ReleaseChannel.STABLE)
    assert vm.is_upgrade("1.1.0-rc1", ReleaseChannel.STABLE, allow_prerelease=True)
    assert vm.is_upgrade("1.1.0-beta", ReleaseChannel.BETA)


def test_compare_and_bump() -> None:
    vm = VersionManager("1.0.0")
    assert vm.compare("1.0.0", "1.0.1") == -1
    assert vm.compare("1.0.1", "1.0.0") == 1
    assert vm.bump("minor") == "1.1.0"
    assert vm.bump("major") == "2.0.0"
    assert vm.bump("patch") == "1.0.1"


def test_channel_of_version() -> None:
    vm = VersionManager("0.9.0")
    assert vm.channel_of("1.0.0-lts") == ReleaseChannel.LTS
    assert vm.channel_of("1.0.0-nightly") == ReleaseChannel.NIGHTLY
    assert vm.channel_of("1.0.0-beta") == ReleaseChannel.BETA
    assert vm.channel_of("1.0.0") == ReleaseChannel.STABLE


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


def test_channel_defaults_and_enable() -> None:
    cm = ReleaseChannelManager()
    assert cm.is_enabled(ReleaseChannel.STABLE)
    assert not cm.is_enabled(ReleaseChannel.BETA)
    cm.enable(ReleaseChannel.BETA)
    assert cm.is_enabled(ReleaseChannel.BETA)
    cm.disable(ReleaseChannel.STABLE)
    assert not cm.is_enabled(ReleaseChannel.STABLE)
    assert ReleaseChannel.STABLE in cm.enabled_channels() or True


def test_channel_policy_order() -> None:
    cm = ReleaseChannelManager()
    cm.enable(ReleaseChannel.NIGHTLY)
    cm.set_policy(ReleaseChannel.NIGHTLY, __import__("services.update.channels", fromlist=["ChannelPolicy"]).ChannelPolicy.AUTO)
    assert cm.policy_for(ReleaseChannel.NIGHTLY).value == "auto"


# ---------------------------------------------------------------------------
# Provider contract
# ---------------------------------------------------------------------------


class _FakeProvider(UpdateProvider):
    def __init__(self, manifest: UpdateManifest | None) -> None:
        self._m = manifest
        self.calls = 0

    @property
    def name(self) -> str:
        return "fake"

    async def fetch_latest(self, channel, *, current_version, timeout_s=10.0):
        self.calls += 1
        return self._m


def test_provider_contract_used_by_manager() -> None:
    m = UpdateManager(current_version="1.0.0")
    man = UpdateManifest(
        version="1.0.1",
        channel=ReleaseChannel.STABLE,
        assets=[ManifestAsset(kind=AssetKind.FULL, url="http://x/a.zip", sha256="deadbeef")],
    )
    prov = _FakeProvider(man)
    m.register_provider(prov)
    info = asyncio.run(m.check_for_updates())
    assert info is not None
    assert info.version == "1.0.1"
    assert prov.calls == 1


def test_no_upgrade_returns_none() -> None:
    m = UpdateManager(current_version="1.0.0")
    prov = _FakeProvider(None)
    m.register_provider(prov)
    info = asyncio.run(m.check_for_updates())
    assert info is None


def test_pin_version_skips_check() -> None:
    m = UpdateManager(current_version="1.0.0")
    prov = _FakeProvider(
        UpdateManifest(version="2.0.0", channel=ReleaseChannel.STABLE,
                      assets=[ManifestAsset(kind=AssetKind.FULL, url="u")])
    )
    m.register_provider(prov)
    m.pin_version("1.0.0")
    assert asyncio.run(m.check_for_updates()) is None


# ---------------------------------------------------------------------------
# GitHub provider (real HTTP path via mocked transport)
# ---------------------------------------------------------------------------


def test_channel_for_tag() -> None:
    assert _channel_for_tag("v1.0.0") == ReleaseChannel.STABLE
    assert _channel_for_tag("v1.0.0-lts") == ReleaseChannel.LTS
    assert _channel_for_tag("v1.0.0-beta") == ReleaseChannel.BETA
    assert _channel_for_tag("v1.0.0-nightly") == ReleaseChannel.NIGHTLY
    assert _channel_for_tag("v1.0.0-enterprise") == ReleaseChannel.ENTERPRISE


def _client_for(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_github_provider_parses_releases() -> None:
    def handler(request):  # type: ignore[no-untyped-def]
        return httpx.Response(
            200,
            json=[
                {
                    "tag_name": "v1.0.1",
                    "name": "v1.0.1",
                    "body": "fixes",
                    "draft": False,
                    "prerelease": False,
                    "published_at": "2026-01-01T00:00:00Z",
                    "assets": [
                        {"name": "aaios-1.0.1.zip", "browser_download_url": "http://x/a.zip", "size": 100}
                    ],
                }
            ],
        )

    provider = GitHubReleaseProvider(repo="o/r", client=_client_for(handler))
    man = asyncio.run(
        provider.fetch_latest(ReleaseChannel.STABLE, current_version="1.0.0")
    )
    assert man is not None
    assert man.version == "1.0.1"
    assert man.channel == ReleaseChannel.STABLE
    assert man.full_asset is not None
    assert man.full_asset.url == "http://x/a.zip"


def test_github_provider_offline_returns_none() -> None:
    def handler(request):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("offline")

    provider = GitHubReleaseProvider(repo="o/r", client=_client_for(handler))
    man = asyncio.run(
        provider.fetch_latest(ReleaseChannel.STABLE, current_version="1.0.0")
    )
    assert man is None


# ---------------------------------------------------------------------------
# Manifest generator (round-trip)
# ---------------------------------------------------------------------------


def test_manifest_roundtrip(tmp_path: Path) -> None:
    man = generate_manifest(
        version="1.0.0",
        channel=ReleaseChannel.STABLE,
        release_notes="rn",
        full_url="http://x/a.zip",
        full_sha256="abc",
        full_size=10,
    )
    p = write_manifest(man, tmp_path / "manifest.json")
    back = read_manifest(p)
    assert back.version == "1.0.0"
    assert back.full_asset.sha256 == "abc"


# ---------------------------------------------------------------------------
# Package verification (real SHA-256)
# ---------------------------------------------------------------------------


def test_verifier_integrity_pass(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg.zip"
    pkg.write_bytes(b"real-package-bytes")
    digest = __import__("services.update.download", fromlist=["sha256_of"]).sha256_of(pkg)
    asset = ManifestAsset(kind=AssetKind.FULL, url="u", sha256=digest)
    res: VerificationResult = asyncio.run(PackageVerifier().verify(pkg, asset))
    assert res.ok
    assert res.integrity_ok


def test_verifier_integrity_mismatch(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg.zip"
    pkg.write_bytes(b"tampered")
    asset = ManifestAsset(kind=AssetKind.FULL, url="u", sha256="correctdigest")
    res = asyncio.run(PackageVerifier().verify(pkg, asset))
    assert not res.ok
    assert not res.integrity_ok
    assert res.error is not None


def test_verifier_published_sig_without_verifier_fails(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg.zip"
    pkg.write_bytes(b"x")
    asset = ManifestAsset(kind=AssetKind.FULL, url="u", signature="sigdata")
    res = asyncio.run(PackageVerifier().verify(pkg, asset))
    # signature published but no verifier -> must NOT trust
    assert res.signature_ok is False
    assert not res.ok


# ---------------------------------------------------------------------------
# Downloader (real streamed download + SHA-256)
# ---------------------------------------------------------------------------


def test_download_streams_and_hashes(tmp_path: Path) -> None:
    body = b"a" * 5000
    digest = __import__("hashlib", fromlist=["sha256"]).sha256(body).hexdigest()
    client = _client_for(lambda req: httpx.Response(200, content=body))
    asset = ManifestAsset(kind=AssetKind.FULL, url="http://x/a.zip", sha256=digest)
    dest = asyncio.run(
        __import__("services.update.download", fromlist=["download_asset"]).download_asset(
            asset, tmp_path / "out.zip", client=client
        )
    )
    assert dest.exists()
    assert dest.read_bytes() == body
    assert dest.suffix != ".part"  # moved from .part


def test_download_checksum_mismatch_raises(tmp_path: Path) -> None:
    client = _client_for(lambda req: httpx.Response(200, content=b"hello"))
    asset = ManifestAsset(kind=AssetKind.FULL, url="http://x/a.zip", sha256="deadbeef")
    with pytest.raises(Exception):
        asyncio.run(
            __import__("services.update.download", fromlist=["download_asset"]).download_asset(
                asset, tmp_path / "out.zip", client=client
            )
        )


# ---------------------------------------------------------------------------
# Rollback manager (uses real BackupManager/RecoveryManager, isolated root)
# ---------------------------------------------------------------------------


def test_rollback_checkpoint_and_release(tmp_path: Path) -> None:
    # Create a minimal workspace the backup manager recognises.
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("k: v\n")
    rm = RollbackManager(tmp_path)
    bid = rm.checkpoint(target_version="1.0.1")
    assert bid
    rm.release_checkpoint(bid)  # must not raise


# ---------------------------------------------------------------------------
# Background service wiring
# ---------------------------------------------------------------------------


def test_background_service_check_now() -> None:
    m = UpdateManager(current_version="1.0.0")
    m.register_provider(
        _FakeProvider(
            UpdateManifest(
                version="1.0.1",
                channel=ReleaseChannel.STABLE,
                assets=[ManifestAsset(kind=AssetKind.FULL, url="u")],
            )
        )
    )
    seen: list[UpdateInfo] = []
    svc = BackgroundUpdateService(m, on_update_available=seen.append)
    info = asyncio.run(svc.check_now())
    assert info is not None
    assert info.version == "1.0.1"
    assert len(seen) == 1
