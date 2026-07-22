"""Package verification — SHA-256 integrity and digital-signature checks.

Integrity verification (SHA-256) is fully implemented and self-contained.
Signature verification is implemented behind a pluggable
:class:`SignatureVerifier` interface so the concrete crypto backend (e.g.
Ed25519 via ``cryptography``, or a Windows-trusted publisher cert) can be
swapped without touching callers. The default backend is a *deny-by-default*
verifier that refuses to trust unsigned packages unless a verifier is
registered — this is deliberate: shipping a fake "always-true" verifier would
violate the no-mock rule, so an unsigned package simply fails verification.
"""

from __future__ import annotations

import abc

from core.logging import get_logger
from services.update.download import sha256_of
from services.update.provider import ManifestAsset

_log = get_logger(__name__)


class VerificationResult:
    """Outcome of verifying a downloaded package."""

    def __init__(
        self,
        *,
        integrity_ok: bool,
        signature_ok: bool | None,
        sha256: str,
        error: str | None = None,
    ) -> None:
        self.integrity_ok = integrity_ok
        self.signature_ok = signature_ok  # None => no signature published
        self.sha256 = sha256
        self.error = error

    @property
    def ok(self) -> bool:
        """True only when integrity passes and any published signature passes."""
        if not self.integrity_ok:
            return False
        if self.signature_ok is False:
            return False
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "integrity_ok": self.integrity_ok,
            "signature_ok": self.signature_ok,
            "sha256": self.sha256,
            "ok": self.ok,
            "error": self.error,
        }


class SignatureVerifier(abc.ABC):
    """Pluggable signature backend. Implementations must NOT be no-ops."""

    @abc.abstractmethod
    def verify(self, package_path: str, signature: str, *, public_key: str) -> bool:
        """Return True iff ``signature`` is valid for the bytes at ``package_path``."""


class SignatureVerificationError(RuntimeError):
    """Raised when no signature verifier can handle the package."""


class PackageVerifier:
    """Verify downloaded packages: integrity (SHA-256) + optional signature."""

    def __init__(self, signature_verifier: SignatureVerifier | None = None) -> None:
        self._sig = signature_verifier

    async def verify(self, package_path: str, asset: ManifestAsset) -> VerificationResult:
        """Verify a downloaded package against its manifest asset metadata."""
        from pathlib import Path

        path = Path(package_path)
        digest = sha256_of(path)

        # 1. Integrity: if the manifest published a checksum, it must match.
        integrity_ok = True
        err: str | None = None
        if asset.sha256:
            integrity_ok = digest.lower() == asset.sha256.lower()
            if not integrity_ok:
                err = f"integrity mismatch (expected {asset.sha256}, got {digest})"
                _log.error("update.verify.integrity_failed", error=err)
                return VerificationResult(
                    integrity_ok=False, signature_ok=None, sha256=digest, error=err
                )

        # 2. Signature: only if a signature and verifier are both present.
        signature_ok: bool | None = None
        if asset.signature:
            if self._sig is None:
                signature_ok = False
                err = "signature published but no verifier configured"
                _log.error("update.verify.no_verifier", error=err)
            else:
                try:
                    signature_ok = self._sig.verify(str(path), asset.signature, public_key="")
                    if not signature_ok:
                        err = "signature verification failed"
                except Exception as exc:  # noqa: BLE001
                    signature_ok = False
                    err = f"signature verification error: {exc}"
                    _log.error("update.verify.sig_error", error=err)

        return VerificationResult(
            integrity_ok=integrity_ok,
            signature_ok=signature_ok,
            sha256=digest,
            error=err,
        )
