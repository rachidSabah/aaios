"""AAiOS Runtime Discovery — real AI runtime discovery, binding & orchestration.

Modules:
  - specs: ProviderSpec registry (35+ AI agent detection recipes)
  - engine: DiscoveryEngine (multi-source layered discovery)
  - validation: ValidationPipeline (14-stage validation)
  - registry: ProviderRegistry (live registry with auto-binding, heartbeat, repair)
"""

from __future__ import annotations

from services.runtime_discovery.engine import (
    DiscoveredProvider,
    DiscoveryEngine,
    DiscoveryResult,
)
from services.runtime_discovery.registry import (
    ProviderRegistry,
    RegisteredProvider,
    get_provider_registry,
)
from services.runtime_discovery.specs import (
    BUILTIN_SPECS,
    AgentCategory,
    DetectionMethod,
    ProviderSpec,
    ProviderSpecRegistry,
    get_spec_registry,
)
from services.runtime_discovery.validation import (
    ValidationPipeline,
    ValidationResult,
    ValidationStage,
)

__all__ = [
    "AgentCategory",
    "BUILTIN_SPECS",
    "DetectionMethod",
    "DiscoveredProvider",
    "DiscoveryEngine",
    "DiscoveryResult",
    "ProviderRegistry",
    "ProviderSpec",
    "ProviderSpecRegistry",
    "RegisteredProvider",
    "ValidationPipeline",
    "ValidationResult",
    "ValidationStage",
    "get_provider_registry",
    "get_spec_registry",
]
