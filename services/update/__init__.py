"""Update manager package."""

from __future__ import annotations

from services.update.manager import UpdateManager
from services.update.models import (
    ReleaseChannel,
    UpdateInfo,
    UpdateReport,
    UpdateStatus,
)

__all__ = [
    "UpdateManager",
    "ReleaseChannel",
    "UpdateInfo",
    "UpdateReport",
    "UpdateStatus",
]
