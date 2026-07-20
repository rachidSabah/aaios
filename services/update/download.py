"""Update downloader — streams packages to disk and computes SHA-256.

Real, side-effecting I/O through ``httpx``. The client is injectable so tests
exercise the full streaming + hashing path without touching the network.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import httpx

from core.logging import get_logger
from services.update.provider import ManifestAsset

_log = get_logger(__name__)

_CHUNK = 1 << 16  # 64 KiB


class DownloadError(RuntimeError):
    """Raised when a download cannot be completed."""


async def download_asset(
    asset: ManifestAsset,
    dest: Path,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = 120.0,
    expected_sha256: str | None = None,
) -> Path:
    """Stream ``asset`` to ``dest`` and verify SHA-256 if ``expected_sha256``.

    Returns the destination path. Raises :class:`DownloadError` on HTTP, I/O,
    or checksum mismatch. If ``expected_sha256`` is provided it MUST match.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    own_client = client is None
    cli = client or httpx.AsyncClient(timeout=timeout_s)
    hasher = hashlib.sha256()
    try:
        async with cli.stream("GET", asset.url) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as fh:
                async for chunk in resp.aiter_bytes(_CHUNK):
                    fh.write(chunk)
                    hasher.update(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"download failed: {exc}") from exc
    finally:
        if own_client:
            await cli.aclose()

    digest = hasher.hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        tmp.unlink(missing_ok=True)
        raise DownloadError(
            f"checksum mismatch: expected {expected_sha256}, got {digest}"
        )

    shutil.move(str(tmp), str(dest))
    _log.info("update.download.completed", url=asset.url, sha256=digest, dest=str(dest))
    return dest


def sha256_of(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file (synchronous, chunked)."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()
