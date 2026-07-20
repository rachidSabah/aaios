"""Version management — semantic-version comparison and channel policy.

Channel-aware upgrade rules (the "automatic update" decision engine):

  STABLE     only moves to higher STABLE versions
  LTS        only moves to higher LTS versions (long-lived, conservative)
  BETA       moves to any BETA/RC >= current on the beta line; never downgrades
  NIGHTLY    moves to any NIGHTLY build newer than current
  ENTERPRISE moves to higher ENTERPRISE versions (default-off unless opted in)

These rules decide *whether* an available manifest is an upgrade for the
installed version. The download/install steps are separate concerns.
"""

from __future__ import annotations

import re
from typing import Any

import semver

from core.logging import get_logger
from services.update.models import ReleaseChannel

_log = get_logger(__name__)

# Optional pre-release/build suffixes are tolerated but ignored for ordering
# when the version is the *stable* component (e.g. "1.0.0-rc1").
_VERSION_RE = re.compile(r"^v?(\d+\.\d+\.\d+(?:[-+].+)?)$")


def parse_version(version: str) -> semver.Version:
    """Parse a version string into a strict ``semver.Version``.

    Strips a leading ``v`` and any channel decoration already removed by the
    provider layer (providers hand us the bare ``X.Y.Z[-suffix]`` form).
    Raises ``ValueError`` on an unparseable string.
    """
    match = _VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(f"Not a semantic version: {version!r}")
    return semver.Version.parse(match.group(1))


def normalize(version: str) -> str:
    """Return the canonical ``X.Y.Z`` (no leading v) for a version string."""
    return str(parse_version(version).replace(prerelease=None, build=None))


class VersionManager:
    """Channel-aware version policy and comparison helpers."""

    def __init__(self, current_version: str) -> None:
        # Current version is whatever is installed; do not normalize the
        # channel suffix away until we need to compare the numeric part.
        self.current_version = current_version

    def is_upgrade(
        self,
        candidate: str,
        channel: ReleaseChannel,
        *,
        allow_prerelease: bool = False,
    ) -> bool:
        """True if ``candidate`` is a genuine upgrade over the installed version.

        Honours channel policy and, for stable/LTS, refuses pre-release
        candidates unless explicitly allowed.
        """
        try:
            cur = parse_version(self.current_version)
            new = parse_version(candidate)
        except ValueError:
            _log.warning(
                "update.version.unparseable",
                current=self.current_version,
                candidate=candidate,
            )
            return False

        # Never downgrade.
        if new <= cur:
            return False

        # Channel policy.
        if channel in (ReleaseChannel.STABLE, ReleaseChannel.LTS):
            if new.prerelease is not None and not allow_prerelease:
                # A stable channel does not auto-adopt pre-releases.
                return False
            return True

        # BETA / NIGHTLY / ENTERPRISE: accept newer, including pre-releases.
        return True

    def compare(self, a: str, b: str) -> int:
        """Return -1/0/1 comparing two version strings numerically."""
        pa, pb = parse_version(a), parse_version(b)
        if pa < pb:
            return -1
        if pa > pb:
            return 1
        return 0

    def bump(
        self, part: str, *, prerelease: str | None = None
    ) -> str:
        """Return the next version by bumping ``major|minor|patch`` of current.

        Useful for the manifest generator and release tooling.
        """
        cur = parse_version(self.current_version)
        if part == "major":
            nxt = cur.bump_major()
        elif part == "minor":
            nxt = cur.bump_minor()
        elif part == "patch":
            nxt = cur.bump_patch()
        else:
            raise ValueError(f"Unknown bump part: {part}")
        if prerelease:
            nxt = nxt.bump_prerelease(prerelease)
        return str(nxt)

    def channel_of(self, version: str) -> ReleaseChannel:
        """Infer the channel from a version string's decoration."""
        v = version.lower()
        if v.endswith("-lts"):
            return ReleaseChannel.LTS
        if "enterprise" in v:
            return ReleaseChannel.ENTERPRISE
        if "nightly" in v:
            return ReleaseChannel.NIGHTLY
        if "beta" in v or "rc" in v:
            return ReleaseChannel.BETA
        return ReleaseChannel.STABLE

    def as_dict(self) -> dict[str, Any]:
        """Serializable snapshot for diagnostics/API responses."""
        return {"current_version": self.current_version}
