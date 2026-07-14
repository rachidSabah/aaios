"""structlog setup — JSON output, correlation IDs, rotating files.

Usage:
    from core.logging import get_logger, bind_context, init_logging

    init_logging(level='INFO', json_output=True, log_file=Path('aaios.log'))
    log = get_logger(__name__)
    log.info('task.submitted', task_id=str(task.id), goal=task.goal)

    # Inside a task handler:
    with bind_context(correlation_id=str(task.id), actor='agent:<id>'):
        log.info('agent.dispatched', capability='code.read')
        # Every log line in this block carries correlation_id + actor
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

# ContextVars carry correlation_id, causation_id, actor through async calls
_CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_CAUSATION_ID: ContextVar[str | None] = ContextVar("causation_id", default=None)
_ACTOR: ContextVar[str | None] = ContextVar("actor", default=None)
# Note: ContextVar default is shared across contexts — callers must NOT mutate it.
# We use None and return a fresh dict on each .get() in the helper below.
_EXTRA: ContextVar[dict[str, Any] | None] = ContextVar("extra", default=None)


def _get_extra() -> dict[str, Any]:
    """Return the current extra dict (a fresh empty dict if unset)."""
    val = _EXTRA.get()
    return val if val is not None else {}


@dataclass
class LoggingConfig:
    """Configuration for the logging system."""

    level: str = "INFO"
    json_output: bool = True
    log_file: Path | None = None
    max_file_size_mb: int = 100
    keep_files: int = 7
    extra_processors: list[Any] = field(default_factory=list)


_INITIALIZED: bool = False
_CONFIG: LoggingConfig | None = None


def init_logging(config: LoggingConfig | None = None) -> None:
    """Initialize structlog + stdlib logging.

    Idempotent: calling more than once is a no-op (subsequent calls update
    the level if different).

    Args:
        config: logging configuration. If None, uses defaults (INFO, JSON
            to stdout, no file).
    """
    global _INITIALIZED, _CONFIG
    if _INITIALIZED and config is None:
        return
    _CONFIG = config or LoggingConfig()

    # Configure stdlib logging first (structlog wraps it)
    stdlib_level = getattr(logging, _CONFIG.level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(stdlib_level)

    # Remove existing handlers (in case init is called twice)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(stdlib_level)
    if _CONFIG.json_output:
        stdout_handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        stdout_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            ),
        )
    root.addHandler(stdout_handler)

    # Optional file handler
    if _CONFIG.log_file is not None:
        _CONFIG.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _CONFIG.log_file,
            maxBytes=_CONFIG.max_file_size_mb * 1024 * 1024,
            backupCount=_CONFIG.keep_files,
            encoding="utf-8",
        )
        file_handler.setLevel(stdlib_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(file_handler)

    # Configure structlog
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _inject_context,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if _CONFIG.json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))
    processors.extend(_CONFIG.extra_processors)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(stdlib_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _INITIALIZED = True


def shutdown_logging() -> None:
    """Flush and close all handlers. Call on system shutdown."""
    global _INITIALIZED, _CONFIG
    if not _INITIALIZED:
        return
    logging.shutdown()
    _INITIALIZED = False
    _CONFIG = None


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to ``name``.

    If logging hasn't been initialized, a default config is used (INFO, JSON
    to stdout). This makes the logger safe to use in tests without explicit
    setup.
    """
    if not _INITIALIZED:
        init_logging()
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


def bind_context(
    *,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    actor: str | None = None,
    **extra: Any,
) -> Any:
    """Bind context values for the current async context.

    Use as a context manager:
        with bind_context(correlation_id=str(task.id)):
            log.info('agent.dispatched')  # carries correlation_id

    Or imperatively (must be cleared manually):
        bind_context(correlation_id=str(task.id))
        log.info('...')
        clear_context()

    Args:
        correlation_id: the task that caused this log/event.
        causation_id: the event that caused this log, if any.
        actor: who is causing this log (e.g. 'agent:<id>').
        **extra: any additional structured fields.
    """
    if correlation_id is not None:
        _CORRELATION_ID.set(correlation_id)
    if causation_id is not None:
        _CAUSATION_ID.set(causation_id)
    if actor is not None:
        _ACTOR.set(actor)
    if extra:
        current = _get_extra()
        merged = {**current, **extra}
        _EXTRA.set(merged)
    return _ContextBinder()


def clear_context() -> None:
    """Clear all context values. Pair with imperative ``bind_context``."""
    _CORRELATION_ID.set(None)
    _CAUSATION_ID.set(None)
    _ACTOR.set(None)
    _EXTRA.set(None)


@contextmanager
def _context_scope() -> Iterator[None]:
    """Restore context on exit (used by _ContextBinder)."""
    extra_val = _EXTRA.get()
    saved = (
        _CORRELATION_ID.get(),
        _CAUSATION_ID.get(),
        _ACTOR.get(),
        dict(extra_val) if extra_val is not None else None,
    )
    try:
        yield
    finally:
        _CORRELATION_ID.set(saved[0])
        _CAUSATION_ID.set(saved[1])
        _ACTOR.set(saved[2])
        _EXTRA.set(saved[3])


class _ContextBinder:
    """Returned by ``bind_context`` to support ``with bind_context(...):``."""

    def __enter__(self) -> _ContextBinder:
        return self

    def __exit__(self, *_: Any) -> None:
        clear_context()


def _inject_context(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor: inject correlation/causation/actor from ContextVars."""
    if (cid := _CORRELATION_ID.get()) is not None:
        event_dict.setdefault("correlation_id", cid)
    if (caid := _CAUSATION_ID.get()) is not None:
        event_dict.setdefault("causation_id", caid)
    if (actor := _ACTOR.get()) is not None:
        event_dict.setdefault("actor", actor)
    extra = _get_extra()
    for k, v in extra.items():
        event_dict.setdefault(k, v)
    return event_dict
