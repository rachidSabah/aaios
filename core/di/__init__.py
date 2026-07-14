"""Dependency Injection container — typed, singleton-scoped, lifecycle-managed.

Single ``Container`` constructed at boot. Owns all service instances and
injects them into agents and supervisors. The container is typed
(mypy-checked) — if a component depends on something that is not
registered, the system fails to boot.

This is the enforcement mechanism for INV-01 (no inner layer instantiating
an outer layer's class). Components are constructed by the container, not
by direct imports.
"""

from __future__ import annotations

from core.di.container import (
    Container,
    LifecycleError,
    Provider,
    Scope,
    get_container,
    init_container,
    reset_container,
)

__all__ = [
    "Container",
    "LifecycleError",
    "Provider",
    "Scope",
    "get_container",
    "init_container",
    "reset_container",
]
