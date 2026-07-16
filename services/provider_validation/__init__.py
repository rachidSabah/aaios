"""Provider Validation Service — live API verification for all 13 LLM providers.

Closes the v1.0 gap: "0 providers live-verified". The validator pings
each registered provider with a minimal completion request and records
status, latency, and error info.
"""

from __future__ import annotations

from services.provider_validation.validator import (
    ProviderValidator,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)

__all__ = [
    "ProviderValidator",
    "ValidationReport",
    "ValidationResult",
    "ValidationStatus",
]
