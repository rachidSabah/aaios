"""Manifest generator — serialize/deserialize a local update manifest.

Produces the JSON document the framework publishes for *offline* and
*enterprise* update scenarios, and the file the installer reads to learn what
was shipped. A generated manifest round-trips through
:class:`~services.update.provider.UpdateManifest` so downstream code never
cares whether the manifest came from GitHub or a local file.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.update.models import ReleaseChannel
from services.update.provider import (
    AssetKind,
    ManifestAsset,
    UpdateManifest,
)


def generate_manifest(
    *,
    version: str,
    channel: ReleaseChannel,
    release_notes: str,
    full_url: str,
    full_sha256: str,
    full_size: int = 0,
    delta_url: str | None = None,
    delta_sha256: str | None = None,
    signature: str | None = None,
    force_upgrade: bool = False,
) -> UpdateManifest:
    """Build a :class:`UpdateManifest` from concrete artifact metadata."""
    assets = [
        ManifestAsset(
            kind=AssetKind.FULL,
            url=full_url,
            size_bytes=full_size,
            sha256=full_sha256,
        )
    ]
    if delta_url and delta_sha256:
        assets.append(
            ManifestAsset(kind=AssetKind.DELTA, url=delta_url, sha256=delta_sha256)
        )
    if signature:
        assets.append(
            ManifestAsset(kind=AssetKind.SIGNATURE, url="", signature=signature)
        )
    return UpdateManifest(
        version=version,
        channel=channel,
        release_notes=release_notes,
        assets=assets,
        force_upgrade=force_upgrade,
    )


def write_manifest(manifest: UpdateManifest, path: Path) -> Path:
    """Persist a manifest as pretty JSON. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_manifest(path: Path) -> UpdateManifest:
    """Load a manifest previously written by :func:`write_manifest`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return UpdateManifest.model_validate(data)
