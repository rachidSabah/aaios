"""Kernel bootstrap — wires the DI container and boots the kernel.

This is the single entry point for bringing the AAiOS kernel online. It:
  1. Initializes logging (structlog + JSON to stdout).
  2. Initializes telemetry (OpenTelemetry).
  3. Loads configuration (defaults.yaml + config.yaml + env + .env + overrides).
  4. Initializes the event bus (with the chosen event store).
  5. Initializes the state manager (subscribes to the bus, registers reducers).
  6. Initializes the platform adapter.
  7. Initializes the Gateway (fs, shell, net).
  8. Initializes the Tool Registry and Prompt Registry.
  9. Emits ``system.booting`` then ``system.ready`` events.

After ``boot_kernel()`` returns, the kernel is ready for the Supervisor
(L4) to be wired in (Phase 8).

Usage:
    from core.bootstrap import boot_kernel, shutdown_kernel

    config = await boot_kernel()
    # ... use the system ...
    await shutdown_kernel()
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.config import ConfigManager, init_config
from core.contracts.actor import ActorRef
from core.contracts.event import Event, EventTopic
from core.di import get_container, init_container, reset_container
from core.event_bus import EventBus, InMemoryEventBus, get_bus, init_bus
from core.event_bus.memory import InMemoryEventStore
from core.logging import LoggingConfig, get_logger, init_logging, shutdown_logging
from core.platform import get_platform
from core.state import StateManager, init_state_manager
from core.state.reducers import DEFAULT_REDUCERS
from core.telemetry import TelemetryConfig, init_telemetry, shutdown_telemetry

_log = get_logger(__name__)


@dataclass
class KernelConfig:
    """Configuration for the kernel bootstrap."""

    yaml_path: Path | None = None
    env_file_path: Path | None = None
    defaults_path: Path | None = None
    overrides: dict[str, Any] | None = None
    log_level: str = "INFO"
    log_file: Path | None = None
    otlp_endpoint: str | None = None
    console_telemetry: bool = False


_INSTANCE_LOCK = asyncio.Lock()
_BOOTED: bool = False
_BOOT_ID: str = ""


async def boot_kernel(config: KernelConfig | None = None) -> ConfigManager:
    """Boot the AAiOS kernel.

    Idempotent: calling more than once is a no-op.

    Args:
        config: kernel configuration. If None, uses defaults (no YAML, no
            .env, no OTLP — just stdout logging and an in-memory event store).

    Returns:
        The initialized ConfigManager.
    """
    global _BOOTED, _BOOT_ID
    async with _INSTANCE_LOCK:
        if _BOOTED:
            _log.info("kernel.already_booted", boot_id=_BOOT_ID)
            return _get_config_or_default()

        config = config or KernelConfig()
        _BOOT_ID = str(uuid4())

        # 1. Logging
        init_logging(
            LoggingConfig(
                level=config.log_level,
                json_output=True,
                log_file=config.log_file,
            ),
        )
        _log.info("kernel.booting", boot_id=_BOOT_ID, python=sys.version.split()[0])

        # 2. Telemetry
        init_telemetry(
            TelemetryConfig(
                otlp_endpoint=config.otlp_endpoint,
                console_export=config.console_telemetry,
                service_instance_id=_BOOT_ID,
            ),
        )

        # 3. Configuration
        cm = init_config(
            yaml_path=config.yaml_path,
            env_file_path=config.env_file_path,
            defaults_path=config.defaults_path,
            overrides=config.overrides,
        )

        # 4. Event bus (in-memory store for Phase 3; SQLite in Phase 8)
        store = InMemoryEventStore()
        bus = init_bus(store=store)

        # 5. State manager + reducers
        state_mgr = init_state_manager(bus=bus)
        for agg_type, reducer in DEFAULT_REDUCERS.items():
            state_mgr.register_reducer(agg_type, reducer)

        # 6. Platform
        platform = get_platform()
        _log.info("kernel.platform", name=platform.name, supported=platform.supported())

        # 7. DI container (registers singletons)
        container = init_container()
        container.register_instance(ConfigManager, cm)
        container.register_instance(EventBus, bus)
        container.register_instance(StateManager, state_mgr)
        await container.boot()

        # 8. Emit system.booting then system.ready
        system_actor = ActorRef.system()
        boot_event = Event(
            topic=EventTopic.SYSTEM_BOOTING,
            correlation_id=uuid4(),
            actor=system_actor,
            payload={"boot_id": _BOOT_ID, "python": sys.version.split()[0]},
        )
        await bus.publish(boot_event)

        ready_event = Event(
            topic=EventTopic.SYSTEM_READY,
            correlation_id=boot_event.correlation_id,
            causation_id=boot_event.id,
            actor=system_actor,
            payload={
                "boot_id": _BOOT_ID,
                "platform": platform.name,
                "event_store": "in_memory",
            },
        )
        await bus.publish(ready_event)

        _BOOTED = True
        _log.info("kernel.ready", boot_id=_BOOT_ID)
        return cm


async def shutdown_kernel() -> None:
    """Shut down the kernel cleanly.

    Emits ``system.shutting_down``, then closes the bus, state manager,
    container, telemetry, and logging in reverse boot order.
    """
    global _BOOTED, _BOOT_ID
    async with _INSTANCE_LOCK:
        if not _BOOTED:
            return

        _log.info("kernel.shutting_down", boot_id=_BOOT_ID)

        # Emit shutdown event
        bus = get_bus()
        system_actor = ActorRef.system()
        await bus.publish(
            Event(
                topic=EventTopic.SYSTEM_SHUTTING_DOWN,
                correlation_id=uuid4(),
                actor=system_actor,
                payload={"boot_id": _BOOT_ID},
            ),
        )

        # Shutdown in reverse boot order
        container = get_container()
        await container.shutdown()
        reset_container()

        # Stop file watchers
        from core.config import get_config

        try:
            cm = get_config()
            await cm.stop_watching()
        except RuntimeError:
            pass

        # Close the bus
        await bus.close()
        from core.event_bus import set_bus

        set_bus(InMemoryEventBus())  # reset singleton to a fresh empty bus

        # Telemetry
        shutdown_telemetry()

        _BOOTED = False
        _BOOT_ID = ""
        shutdown_logging()


def is_booted() -> bool:
    """Return True if the kernel has been booted."""
    return _BOOTED


def boot_id() -> str:
    """Return the current boot ID (empty if not booted)."""
    return _BOOT_ID


def _get_config_or_default() -> ConfigManager:
    """Return the current ConfigManager, or initialize a default one."""
    try:
        from core.config import get_config

        return get_config()
    except RuntimeError:
        return init_config()


# ---------------------------------------------------------------------------
# CLI entry point: python -m core.bootstrap
# ---------------------------------------------------------------------------


async def _main() -> int:
    """Boot the kernel, print 'AAiOS kernel ready', and shut down."""
    await boot_kernel()
    log = get_logger(__name__)
    log.info("kernel.main_ready", boot_id=_BOOT_ID)
    print(f"AAiOS kernel ready (boot_id={_BOOT_ID})")
    await shutdown_kernel()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
