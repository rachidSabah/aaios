"""Tests for core.bootstrap — kernel boot and shutdown."""

from __future__ import annotations

import pytest

from core.bootstrap import boot_id, boot_kernel, is_booted, shutdown_kernel
from core.contracts.event import EventTopic
from core.event_bus import get_bus


@pytest.mark.offline
class TestKernelBoot:
    """Kernel bootstrap tests."""

    async def test_boot_and_shutdown(self) -> None:
        """The kernel boots, emits events, and shuts down cleanly."""
        await boot_kernel()
        assert is_booted() is True
        assert boot_id() != ""

        # The bus should have received system.booting and system.ready
        bus = get_bus()
        events = await bus.store.replay()
        topics = [e.topic for e in events]
        assert EventTopic.SYSTEM_BOOTING in topics
        assert EventTopic.SYSTEM_READY in topics

        await shutdown_kernel()
        assert is_booted() is False
        assert boot_id() == ""

    async def test_boot_is_idempotent(self) -> None:
        """Calling boot_kernel twice doesn't re-boot."""
        await boot_kernel()
        first_id = boot_id()
        await boot_kernel()  # no-op
        assert boot_id() == first_id
        await shutdown_kernel()

    async def test_shutdown_without_boot_is_noop(self) -> None:
        """Shutting down without booting is safe."""
        assert is_booted() is False
        await shutdown_kernel()  # should not raise
        assert is_booted() is False

    async def test_boot_loads_config(self) -> None:
        """Booting the kernel initializes the config manager."""
        from core.bootstrap import KernelConfig
        from core.config import get_config

        await boot_kernel(KernelConfig(overrides={"test.key": "test.value"}))
        cm = get_config()
        assert cm.get("test.key") == "test.value"
        await shutdown_kernel()

    async def test_boot_registers_default_reducers(self) -> None:
        """The Task reducer is registered during boot."""
        from core.state.reducers import DEFAULT_REDUCERS

        await boot_kernel()
        from core.state import get_state_manager

        sm = get_state_manager()
        for agg_type in DEFAULT_REDUCERS:
            assert agg_type in sm._reducers
        await shutdown_kernel()
