"""DI container implementation.

A minimal, typed DI container. Supports:
  - ``singleton`` scope (default; one instance per container)
  - ``transient`` scope (new instance per call)
  - ``factory`` providers (callable that returns the instance)
  - ``instance`` providers (pre-built instance)
  - ``boot()`` lifecycle hook (construct all singletons eagerly)
  - ``shutdown()`` lifecycle hook (call ``aclose()`` on instances that have it)

The container is not thread-safe in the strictest sense, but it's only
mutated during boot/shutdown, which are single-threaded by convention.
Read access (``get()``) is safe from any async context after boot.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)


class Scope(StrEnum):
    """Provider scope."""

    SINGLETON = "singleton"  # one instance per container
    TRANSIENT = "transient"  # new instance per get()


@dataclass
class Provider:
    """A registered provider."""

    interface: type
    factory: Callable[..., Any]
    scope: Scope = Scope.SINGLETON
    instance: Any | None = None  # for SINGLETON, once built
    name: str = ""


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation fails."""


class Container:
    """The DI container.

    Usage:
        container = Container()
        container.register(IEventBus, factory=lambda: InMemoryEventBus(), scope=Scope.SINGLETON)
        await container.boot()
        bus = container.get(IEventBus)
        ...
        await container.shutdown()
    """

    def __init__(self) -> None:
        self._providers: dict[type, Provider] = {}
        self._singletons: dict[type, Any] = {}
        self._boot_order: list[type] = []
        self._booted = False

    def register(
        self,
        interface: type,
        factory: Callable[..., Any],
        *,
        scope: Scope = Scope.SINGLETON,
        name: str = "",
    ) -> None:
        """Register a provider.

        Args:
            interface: the type to register under (used for ``get()``).
            factory: callable that returns the instance. May be sync or async;
                may take dependencies (typed arguments resolved by the container).
            scope: SINGLETON (default) or TRANSIENT.
            name: optional human-readable name (for error messages).
        """
        if interface in self._providers:
            raise LifecycleError(f"Interface {interface!r} already registered.")
        self._providers[interface] = Provider(
            interface=interface,
            factory=factory,
            scope=scope,
            name=name or interface.__name__,
        )

    def register_instance(self, interface: type, instance: Any, *, name: str = "") -> None:
        """Register a pre-built instance (always singleton)."""
        if interface in self._providers:
            raise LifecycleError(f"Interface {interface!r} already registered.")
        provider = Provider(
            interface=interface,
            factory=lambda: instance,
            scope=Scope.SINGLETON,
            instance=instance,
            name=name or interface.__name__,
        )
        self._providers[interface] = provider
        self._singletons[interface] = instance

    def get(self, interface: type) -> Any:
        """Return an instance of ``interface``.

        For SINGLETON scope, returns the cached instance (building it on
        first access if ``boot()`` hasn't been called).

        For TRANSIENT scope, builds a new instance each call.
        """
        provider = self._providers.get(interface)
        if provider is None:
            raise LifecycleError(
                f"Interface {interface!r} not registered. "
                f"Available: {list(self._providers.keys())}",
            )

        if provider.scope == Scope.SINGLETON:
            if interface in self._singletons:
                return self._singletons[interface]
            instance = self._build(provider)
            self._singletons[interface] = instance
            return instance

        return self._build(provider)

    def has(self, interface: type) -> bool:
        """Return True if ``interface`` is registered."""
        return interface in self._providers

    def list_interfaces(self) -> list[type]:
        """Return all registered interfaces."""
        return list(self._providers.keys())

    def _build(self, provider: Provider) -> Any:
        """Build an instance from a provider, resolving dependencies."""
        # Introspect the factory's signature
        sig = inspect.signature(provider.factory)
        kwargs: dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if name == "self" or param.annotation is inspect.Parameter.empty:
                continue
            annotation = param.annotation
            if isinstance(annotation, type) and annotation in self._providers:
                kwargs[name] = self.get(annotation)
        try:
            result = provider.factory(**kwargs)
        except TypeError as e:
            raise LifecycleError(
                f"Failed to build {provider.name}: factory call failed: {e}",
            ) from e
        if asyncio.iscoroutine(result):
            # Async factory — run it synchronously (we're in boot)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(result)
        return result

    async def boot(self) -> None:
        """Build all SINGLETON providers eagerly.

        Useful for catching wiring errors at boot rather than at first use.
        After boot, ``get()`` is a pure lookup (no factory invocation).
        """
        if self._booted:
            return
        # Build in registration order (callers should register in dependency order)
        for interface, provider in self._providers.items():
            if provider.scope != Scope.SINGLETON:
                continue
            if interface in self._singletons:
                continue  # pre-registered instance
            instance = await self._build_async(provider)
            self._singletons[interface] = instance
            self._boot_order.append(interface)
            _log.info("di.booted", interface=provider.name)
        self._booted = True
        _log.info("di.boot_complete", singletons=len(self._singletons))

    async def _build_async(self, provider: Provider) -> Any:
        """Build an instance, supporting async factories."""
        sig = inspect.signature(provider.factory)
        kwargs: dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if name == "self" or param.annotation is inspect.Parameter.empty:
                continue
            annotation = param.annotation
            if isinstance(annotation, type) and annotation in self._providers:
                kwargs[name] = self.get(annotation)
        try:
            result = provider.factory(**kwargs)
        except TypeError as e:
            raise LifecycleError(
                f"Failed to build {provider.name}: factory call failed: {e}",
            ) from e
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def shutdown(self) -> None:
        """Shut down all singletons in reverse boot order.

        Calls ``aclose()`` on instances that have it (async context managers).
        """
        for interface in reversed(self._boot_order):
            instance = self._singletons.pop(interface, None)
            if instance is None:
                continue
            aclose = getattr(instance, "aclose", None) or getattr(instance, "close", None)
            if aclose is None:
                continue
            try:
                result = aclose()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                _log.exception(
                    "di.shutdown_failed", interface=getattr(interface, "__name__", str(interface))
                )
        self._booted = False
        self._boot_order.clear()


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_INSTANCE: Container | None = None


def init_container() -> Container:
    """Initialize the global container."""
    global _INSTANCE
    _INSTANCE = Container()
    return _INSTANCE


def get_container() -> Container:
    """Return the global container."""
    if _INSTANCE is None:
        raise RuntimeError("Container not initialized. Call init_container() first.")
    return _INSTANCE


def reset_container() -> None:
    """Reset the global container (for tests)."""
    global _INSTANCE
    _INSTANCE = None
