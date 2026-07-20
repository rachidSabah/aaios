"""Update framework package — provider-based, GitHub-agnostic.

Public surface: the orchestrator (:class:`UpdateManager`), the provider
contract (:class:`UpdateProvider`), the channel manager, and the models.
Everything else (download, verify, rollback, manifest, version, service) is
importable from submodules.
"""

from __future__ import annotations

from services.update.channels import ChannelPolicy, ReleaseChannelManager
from services.update.manager import UpdateError, UpdateManager
from services.update.models import (
    ReleaseChannel,
    UpdateInfo,
    UpdateReport,
    UpdateStatus,
)
from services.update.provider import (
    AssetKind,
    ManifestAsset,
    UpdateManifest,
    UpdateProvider,
)
from services.update.rollback import RollbackError, RollbackManager
from services.update.service import BackgroundUpdateService
from services.update.verify import PackageVerifier, VerificationResult

__all__ = [
    "AssetKind",
    "BackgroundUpdateService",
    "ChannelPolicy",
    "ManifestAsset",
    "PackageVerifier",
    "ReleaseChannel",
    "ReleaseChannelManager",
    "RollbackError",
    "RollbackManager",
    "UpdateError",
    "UpdateInfo",
    "UpdateManager",
    "UpdateManifest",
    "UpdateProvider",
    "UpdateReport",
    "UpdateStatus",
    "VerificationResult",
]
