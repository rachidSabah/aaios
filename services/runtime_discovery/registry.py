"""Live Provider Registry — auto-binding, heartbeat, monitoring, auto-repair.

The registry is the single source of truth for all discovered AI providers.
It:
  - Discovers providers via the DiscoveryEngine
  - Validates each via the ValidationPipeline
  - Binds valid providers (makes them available)
  - Monitors health via periodic heartbeats
  - Auto-repairs unhealthy providers
  - Broadcasts changes via the EventBus

No provider is hardcoded. No provider is mocked. Every provider in the
registry was discovered on the host.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.logging import get_logger
from services.runtime_discovery.engine import (
    DiscoveredProvider,
    DiscoveryEngine,
    DiscoveryResult,
)
from services.runtime_discovery.specs import (
    ProviderSpec,
    ProviderSpecRegistry,
    get_spec_registry,
)
from services.runtime_discovery.validation import ValidationPipeline, ValidationResult

_log = get_logger(__name__)

__all__ = [
    "RegisteredProvider",
    "ProviderRegistry",
    "get_provider_registry",
]


@dataclass
class RegisteredProvider:
    """A provider that has been discovered, validated, and bound."""

    provider_id: str = field(default_factory=lambda: uuid4().hex[:12])
    spec_id: str = ""
    name: str = ""
    vendor: str = ""
    category: str = ""
    description: str = ""
    executable: str = ""
    version: str = ""
    install_path: str = ""
    detection_method: str = ""
    package_manager: str = ""
    config_file: str = ""
    icon: str = ""
    license: str = ""
    website: str = ""

    # Health
    health: str = "unknown"  # unknown | healthy | unhealthy | validating | repairing
    validated: bool = False
    last_validated_at: str = ""
    latency_ms: float = 0.0

    # Capabilities
    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)

    # Runtime metrics (updated by heartbeat)
    cpu_pct: float = 0.0
    ram_pct: float = 0.0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    # State
    bound: bool = False
    bound_at: str = ""
    last_heartbeat: str = ""
    error: str | None = None

    # Validation details
    validation_stages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "spec_id": self.spec_id,
            "name": self.name,
            "vendor": self.vendor,
            "category": self.category,
            "description": self.description,
            "executable": self.executable,
            "version": self.version,
            "install_path": self.install_path,
            "detection_method": self.detection_method,
            "package_manager": self.package_manager,
            "config_file": self.config_file,
            "icon": self.icon,
            "license": self.license,
            "website": self.website,
            "health": self.health,
            "validated": self.validated,
            "last_validated_at": self.last_validated_at,
            "latency_ms": round(self.latency_ms, 2),
            "capabilities": list(self.capabilities),
            "models": list(self.models),
            "cpu_pct": round(self.cpu_pct, 2),
            "ram_pct": round(self.ram_pct, 2),
            "running_tasks": self.running_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "bound": self.bound,
            "bound_at": self.bound_at,
            "last_heartbeat": self.last_heartbeat,
            "error": self.error,
            "validation_stages": list(self.validation_stages),
        }


class ProviderRegistry:
    """Live provider registry with auto-binding and monitoring.

    Usage:
        registry = get_provider_registry()
        await registry.discover()  # Scan the host
        providers = registry.list_providers()
    """

    def __init__(
        self,
        discovery_engine: DiscoveryEngine | None = None,
        validation_pipeline: ValidationPipeline | None = None,
        spec_registry: ProviderSpecRegistry | None = None,
    ) -> None:
        self._discovery = discovery_engine or DiscoveryEngine()
        self._validation = validation_pipeline or ValidationPipeline()
        self._specs = spec_registry or get_spec_registry()
        self._providers: dict[str, RegisteredProvider] = {}
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._last_scan: DiscoveryResult | None = None

    async def discover(self) -> DiscoveryResult:
        """Run a full discovery scan and bind all valid providers."""
        _log.info("provider_registry.discover_start")
        result = await self._discovery.discover_all()
        self._last_scan = result

        # Validate and bind each discovered provider
        for discovered in result.providers:
            await self._validate_and_bind(discovered)

        _log.info(
            "provider_registry.discover_complete",
            discovered=len(result.providers),
            bound=len([p for p in self._providers.values() if p.bound]),
        )
        return result

    def list_providers(
        self,
        *,
        category: str | None = None,
        health: str | None = None,
        bound_only: bool = False,
    ) -> list[RegisteredProvider]:
        """List all registered providers."""
        out = list(self._providers.values())
        if category:
            out = [p for p in out if p.category == category]
        if health:
            out = [p for p in out if p.health == health]
        if bound_only:
            out = [p for p in out if p.bound]
        return out

    def get_provider(self, provider_id: str) -> RegisteredProvider | None:
        return self._providers.get(provider_id)

    def get_by_spec(self, spec_id: str) -> RegisteredProvider | None:
        for p in self._providers.values():
            if p.spec_id == spec_id:
                return p
        return None

    async def rebind(self, provider_id: str) -> bool:
        """Re-bind a provider (re-validate and re-bind)."""
        provider = self._providers.get(provider_id)
        if not provider:
            return False
        spec = self._specs.get(provider.spec_id)
        if not spec:
            return False
        provider.health = "validating"
        validation = await self._validation.validate(
            provider.provider_id, provider.executable, spec
        )
        self._apply_validation(provider, validation, spec)
        return provider.bound

    async def unbind(self, provider_id: str) -> bool:
        """Unbind a provider."""
        provider = self._providers.get(provider_id)
        if not provider:
            return False
        provider.bound = False
        provider.health = "offline"
        _log.info("provider_registry.unbind", provider=provider_id)
        return True

    async def self_test(self, provider_id: str) -> dict[str, Any]:
        """Run a self-test on a provider."""
        provider = self._providers.get(provider_id)
        if not provider:
            return {"error": "provider not found"}
        spec = self._specs.get(provider.spec_id)
        if not spec:
            return {"error": "spec not found"}
        validation = await self._validation.validate(
            provider.provider_id, provider.executable, spec
        )
        return validation.to_dict()

    async def restart(self, provider_id: str) -> bool:
        """Restart a provider (re-validate)."""
        return await self.rebind(provider_id)

    async def repair(self, provider_id: str) -> bool:
        """Attempt to repair an unhealthy provider."""
        provider = self._providers.get(provider_id)
        if not provider:
            return False
        provider.health = "repairing"
        spec = self._specs.get(provider.spec_id)
        if not spec:
            return False
        # Re-discover
        discovered = await self._discovery.discover_one(provider.spec_id)
        if discovered:
            # Re-validate
            for d in discovered:
                validation = await self._validation.validate(
                    provider.provider_id, d.executable, spec
                )
                if validation.overall_passed:
                    provider.executable = d.executable
                    provider.version = d.version
                    provider.health = "healthy"
                    provider.bound = True
                    provider.error = None
                    return True
        provider.health = "unhealthy"
        return False

    def delete(self, provider_id: str) -> bool:
        """Remove a provider from the registry."""
        if provider_id not in self._providers:
            return False
        del self._providers[provider_id]
        _log.info("provider_registry.delete", provider=provider_id)
        return True

    def stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        providers = list(self._providers.values())
        by_health: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for p in providers:
            by_health[p.health] = by_health.get(p.health, 0) + 1
            by_category[p.category] = by_category.get(p.category, 0) + 1
        return {
            "total": len(providers),
            "bound": sum(1 for p in providers if p.bound),
            "healthy": sum(1 for p in providers if p.health == "healthy"),
            "unhealthy": sum(1 for p in providers if p.health == "unhealthy"),
            "by_health": by_health,
            "by_category": by_category,
            "last_scan": self._last_scan.to_dict() if self._last_scan else None,
        }

    # --- Heartbeat / Monitoring -----------------------------------------

    async def start_heartbeat(self, interval_s: float = 30.0) -> None:
        """Start periodic heartbeat monitoring."""
        if self._heartbeat_task:
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval_s))

    async def stop_heartbeat(self) -> None:
        """Stop heartbeat monitoring."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self, interval_s: float) -> None:
        """Periodically check provider health."""
        while True:
            try:
                await asyncio.sleep(interval_s)
                await self._run_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                _log.warning("provider_registry.heartbeat_error", error=str(e))

    async def _run_heartbeat(self) -> None:
        """Check all bound providers."""
        for provider in list(self._providers.values()):
            if not provider.bound:
                continue
            spec = self._specs.get(provider.spec_id)
            if not spec:
                continue
            # Quick health check
            validation = await self._validation.validate(
                provider.provider_id, provider.executable, spec
            )
            if not validation.overall_passed and provider.health == "healthy":
                _log.warning(
                    "provider_registry.heartbeat_unhealthy",
                    provider=provider.provider_id,
                )
                # Attempt auto-repair
                await self.repair(provider.provider_id)
            provider.last_heartbeat = datetime.now(UTC).isoformat()
            provider.latency_ms = validation.latency_ms

    # --- Internal helpers -----------------------------------------------

    async def _validate_and_bind(self, discovered: DiscoveredProvider) -> None:
        """Validate a discovered provider and bind it if valid."""
        spec = self._specs.get(discovered.spec_id)
        if not spec:
            return

        # Check if already registered (update existing)
        existing = self.get_by_spec(discovered.spec_id)
        if existing:
            # Update with new discovery info
            existing.executable = discovered.executable or existing.executable
            existing.version = discovered.version or existing.version
            existing.install_path = discovered.install_path or existing.install_path
            existing.detection_method = discovered.detection_method or existing.detection_method
            existing.health = "healthy" if discovered.health != "unhealthy" else "unhealthy"
            existing.last_heartbeat = datetime.now(UTC).isoformat()
            return

        # Create new provider
        provider = RegisteredProvider(
            spec_id=discovered.spec_id,
            name=discovered.name,
            vendor=discovered.vendor,
            category=discovered.category,
            description=spec.description,
            executable=discovered.executable,
            version=discovered.version,
            install_path=discovered.install_path,
            detection_method=discovered.detection_method,
            package_manager=discovered.package_manager,
            config_file=discovered.config_file,
            icon=spec.icon,
            license=spec.license,
            website=spec.website,
            capabilities=list(discovered.capabilities or spec.expected_capabilities),
            health="validating",
        )
        self._providers[provider.provider_id] = provider

        # Validate
        validation = await self._validation.validate(
            provider.provider_id, provider.executable, spec
        )
        self._apply_validation(provider, validation, spec)

    def _apply_validation(
        self,
        provider: RegisteredProvider,
        validation: ValidationResult,
        spec: ProviderSpec,
    ) -> None:
        """Apply validation results to a provider."""
        provider.validated = True
        provider.last_validated_at = validation.validated_at
        provider.validation_stages = [s.to_dict() for s in validation.stages]
        provider.latency_ms = validation.latency_ms
        provider.health = validation.health
        provider.capabilities = validation.capabilities or list(spec.expected_capabilities)
        provider.models = validation.models
        provider.bound = validation.overall_passed
        provider.bound_at = datetime.now(UTC).isoformat() if provider.bound else ""
        provider.error = validation.error
        _log.info(
            "provider_registry.provider_validated",
            provider=provider.name,
            passed=validation.overall_passed,
            health=provider.health,
        )


# Singleton
_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
