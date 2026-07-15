"""Provider Validation Agent — live API verification for all 13 LLM providers.

For each registered provider, the validator:
  1. Sends a minimal "ping" completion request (1 token, "ping" prompt)
  2. Records: status (ok/unauthorized/rate_limited/timeout/unreachable),
     latency_ms, model used, error message
  3. Optionally lists available models (where the provider supports it)
  4. Returns a structured validation matrix

This closes the v1.0 gap: "0 providers live-verified". After running the
validator, users get a clear report of which providers actually work with
their configured API keys.

Usage:
    validator = ProviderValidator()
    report = await validator.validate_all()
    for r in report.results:
        print(f"{r.provider}: {r.status} ({r.latency_ms} ms)")
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.contracts.model.message import ModelMessage
from core.contracts.model.request import ModelRequest
from core.contracts.provider import ProviderConfig, ProviderType
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "ProviderValidator",
    "ValidationReport",
    "ValidationResult",
    "ValidationStatus",
]


class ValidationStatus:
    """Validation outcome status."""

    OK = "ok"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN_ERROR = "unknown_error"


# Default probe model per provider — the cheapest model that should always
# respond to a 1-token ping. Users can override via ProviderConfig.models.
_PROBE_MODELS: dict[ProviderType, str] = {
    ProviderType.OPENAI: "gpt-4o-mini",
    ProviderType.ANTHROPIC: "claude-3-5-haiku-20241022",
    ProviderType.GOOGLE: "gemini-1.5-flash",
    ProviderType.OPENROUTER: "openai/gpt-4o-mini",
    ProviderType.DEEPSEEK: "deepseek-chat",
    ProviderType.GLM: "glm-4-flash",
    ProviderType.NVIDIA: "meta/llama-3.1-8b-instruct",
    ProviderType.OLLAMA: "llama3.2",
    ProviderType.LM_STUDIO: "local-model",
    ProviderType.AZURE_OPENAI: "gpt-4o-mini",
    ProviderType.MISTRAL: "mistral-small-latest",
    ProviderType.GROQ: "llama-3.1-8b-instant",
    ProviderType.CUSTOM: "",
}


# Type for a provider factory — given a ProviderConfig, returns an object
# with an async `complete(request)` method.
ProviderFactory = Callable[[ProviderConfig], Any]


@dataclass
class ValidationResult:
    """Result of validating a single provider."""

    provider: str
    provider_type: ProviderType
    status: str
    latency_ms: float | None = None
    model_used: str | None = None
    response_preview: str | None = None
    error: str | None = None
    validated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_type": str(self.provider_type),
            "status": self.status,
            "latency_ms": self.latency_ms,
            "model_used": self.model_used,
            "response_preview": self.response_preview,
            "error": self.error,
            "validated_at": self.validated_at,
        }


@dataclass
class ValidationReport:
    """Aggregate report across all providers."""

    results: list[ValidationResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    total_providers: int = 0
    ok_count: int = 0
    failed_count: int = 0
    not_configured_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_providers": self.total_providers,
            "ok_count": self.ok_count,
            "failed_count": self.failed_count,
            "not_configured_count": self.not_configured_count,
        }


class _MockProvider:
    """Mock provider for testing — returns a canned response."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    async def complete(self, request: ModelRequest) -> Any:
        # Return a minimal response-like object with `content`
        class _Resp:
            content = "pong"

        return _Resp()


class ProviderValidator:
    """Validates that configured LLM providers actually work.

    The validator takes a list of ProviderConfig objects (or queries the
    global ModelRouter for them) and pings each one with a minimal request.

    A `provider_factory` can be injected to override the default class
    lookup — useful for testing.
    """

    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        probe_prompt: str = "ping",
        max_output_tokens: int = 1,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._probe_prompt = probe_prompt
        self._max_output_tokens = max_output_tokens
        self._provider_factory = provider_factory

    async def validate_provider(
        self,
        config: ProviderConfig,
    ) -> ValidationResult:
        """Validate a single provider config.

        Returns a ValidationResult with status OK / UNAUTHORIZED / etc.
        """
        if not config.enabled:
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=ValidationStatus.NOT_CONFIGURED,
                error="Provider is disabled",
            )
        if config.api_key is None and config.type not in (
            ProviderType.OLLAMA,
            ProviderType.LM_STUDIO,
        ):
            # Local providers (Ollama, LM Studio) don't need an API key
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=ValidationStatus.NOT_CONFIGURED,
                error="No API key configured",
            )

        # Choose the probe model
        probe_model = (
            config.models[0] if config.models else _PROBE_MODELS.get(config.type, "")
        )
        if not probe_model:
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=ValidationStatus.NOT_CONFIGURED,
                error="No probe model available for this provider type",
            )

        # Build a minimal request
        request = ModelRequest(
            messages=[ModelMessage.user(self._probe_prompt)],
            model_hint=probe_model,
            max_tokens=self._max_output_tokens,
            temperature=0.0,
        )

        # Get or instantiate the provider
        try:
            provider = self._get_provider(config)
        except Exception as e:
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=ValidationStatus.UNKNOWN_ERROR,
                error=f"Failed to instantiate provider: {e}",
            )

        start = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                provider.complete(request),
                timeout=self._timeout_s,
            )
            latency_ms = (time.perf_counter() - start) * 1000.0
            preview = (getattr(response, "content", "") or "")[:80]
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=ValidationStatus.OK,
                latency_ms=round(latency_ms, 2),
                model_used=probe_model,
                response_preview=preview,
            )
        except TimeoutError:
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=ValidationStatus.TIMEOUT,
                error=f"Provider did not respond within {self._timeout_s}s",
            )
        except Exception as e:
            status, msg = self._classify_error(e)
            return ValidationResult(
                provider=config.name,
                provider_type=config.type,
                status=status,
                error=msg,
            )

    def _get_provider(self, config: ProviderConfig) -> Any:
        """Get or instantiate a provider instance for the config."""
        if self._provider_factory is not None:
            return self._provider_factory(config)
        from services.model_router.router import _PROVIDER_CLASSES

        provider_cls = _PROVIDER_CLASSES.get(config.type)
        if provider_cls is None:
            raise RuntimeError(
                f"No provider class registered for {config.type}",
            )
        return provider_cls(config)

    def _classify_error(self, e: Exception) -> tuple[str, str]:
        """Classify an exception into a ValidationStatus + message."""
        msg = str(e)
        msg_lower = msg.lower()
        # Check for common auth errors
        if any(
            s in msg_lower
            for s in ("401", "unauthorized", "invalid api key", "invalid_api_key")
        ):
            return ValidationStatus.UNAUTHORIZED, msg
        if any(s in msg_lower for s in ("403", "forbidden", "permission")):
            return ValidationStatus.UNAUTHORIZED, msg
        if any(
            s in msg_lower
            for s in ("429", "rate limit", "rate_limit", "too many requests")
        ):
            return ValidationStatus.RATE_LIMITED, msg
        if any(
            s in msg_lower
            for s in ("connection", "unreachable", "refused", "dns", "name resolution")
        ):
            return ValidationStatus.UNREACHABLE, msg
        return ValidationStatus.UNKNOWN_ERROR, msg

    async def validate_all(
        self,
        configs: list[ProviderConfig] | None = None,
    ) -> ValidationReport:
        """Validate all (or the given) providers in parallel.

        If configs is None, attempts to fetch them from the global
        ModelRouter instance.
        """
        if configs is None:
            configs = self._configs_from_router()
        started = datetime.now(UTC)
        # Run all validations in parallel
        tasks = [self.validate_provider(c) for c in configs]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        finished = datetime.now(UTC)
        ok = sum(1 for r in results if r.status == ValidationStatus.OK)
        not_configured = sum(
            1 for r in results if r.status == ValidationStatus.NOT_CONFIGURED
        )
        failed = len(results) - ok - not_configured
        return ValidationReport(
            results=list(results),
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            total_providers=len(results),
            ok_count=ok,
            failed_count=failed,
            not_configured_count=not_configured,
        )

    def _configs_from_router(self) -> list[ProviderConfig]:
        """Try to fetch provider configs from the global ModelRouter."""
        try:
            from services.model_router import get_model_router

            router = get_model_router()
            # The router stores configs internally; we expose them via this method
            # If the router doesn't expose configs, return empty list
            configs = getattr(router, "_configs", {})
            if isinstance(configs, dict):
                return list(configs.values())
            if isinstance(configs, list):
                return configs
            return []
        except RuntimeError:
            _log.debug("ModelRouter not initialized — no configs to validate")
            return []
        except Exception as e:
            _log.warning("Failed to fetch configs from router: %s", e)
            return []

