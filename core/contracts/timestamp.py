"""Timestamp helpers shared across the system.

We always use UTC-aware datetimes. Never naive datetimes. Never floats.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utc_now().isoformat()
