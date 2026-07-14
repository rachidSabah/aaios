"""Structured JSON logging with correlation/causation IDs.

Every log entry has:
  - timestamp (UTC, ISO-8601)
  - level (debug, info, warning, error, critical)
  - logger name (module path)
  - message (human-readable)
  - event_id (UUID, optional — links to an Event on the bus)
  - correlation_id (the task that caused this log)
  - causation_id (the event that caused this log, if any)
  - structured payload (free-form dict)

Logs and events share the same ID space, so a log entry can be
cross-referenced to an event and vice versa.

Configuration: see ``core.config`` — keys ``logging.level``, ``logging.format``,
``logging.file.path``, ``logging.file.max_size_mb``, ``logging.file.keep``.
"""

from __future__ import annotations

from core.logging.setup import (
    LoggingConfig,
    bind_context,
    clear_context,
    get_logger,
    init_logging,
    shutdown_logging,
)

__all__ = [
    "LoggingConfig",
    "bind_context",
    "clear_context",
    "get_logger",
    "init_logging",
    "shutdown_logging",
]
