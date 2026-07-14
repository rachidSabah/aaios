"""Model Router — the centralized LLM access layer.

Agents never call providers directly. They construct a ModelRequest and
call ``router.complete(request)`` or ``router.stream(request)``. The router:

  1. Selects the best provider + model based on hints, health, cost, priority
  2. Checks the rate limiter
  3. Calls the provider
  4. On failure: retries (if retryable), then fails over to the next provider
  5. Records cost in the cost ledger
  6. Updates the provider's health state
  7. Returns the response

If all providers fail, raises ProviderError.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from core.contracts.model.health import ProviderHealth, ProviderStatus
from core.contracts.model.request import ModelRequest, RequestHint
from core.contracts.model.response import ModelResponse, ModelStreamChunk
from core.contracts.provider import (
    ModelInfo,
    ModelProvider,
    ProviderConfig,
    ProviderError,
    ProviderHealthState,
    ProviderType,
    RateLimitError,
)
from core.logging import get_logger
from services.model_router.cost_ledger import CostLedger
from services.model_router.providers.anthropic_provider import AnthropicProvider
from services.model_router.providers.azure_openai_provider import AzureOpenAIProvider
from services.model_router.providers.custom_provider import CustomProvider
from services.model_router.providers.deepseek_provider import DeepSeekProvider
from services.model_router.providers.glm_provider import GLMProvider
from services.model_router.providers.google_provider import GoogleProvider
from services.model_router.providers.groq_provider import GroqProvider
from services.model_router.providers.lm_studio_provider import LMStudioProvider
from services.model_router.providers.mistral_provider import MistralProvider
from services.model_router.providers.nvidia_provider import NVIDIAProvider
from services.model_router.providers.ollama_provider import OllamaProvider
from services.model_router.providers.openai_provider import OpenAIProvider
from services.model_router.providers.openrouter_provider import OpenRouterProvider
from services.model_router.rate_limiter import RateLimiter

_log = get_logger(__name__)

__all__ = ["ModelRouter", "get_model_router", "init_model_router", "set_model_router"]

# Provider type → class mapping
_PROVIDER_CLASSES: dict[ProviderType, type] = {
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.GOOGLE: GoogleProvider,
    ProviderType.OPENROUTER: OpenRouterProvider,
    ProviderType.DEEPSEEK: DeepSeekProvider,
    ProviderType.GLM: GLMProvider,
    ProviderType.NVIDIA: NVIDIAProvider,
    ProviderType.OLLAMA: OllamaProvider,
    ProviderType.LM_STUDIO: LMStudioProvider,
    ProviderType.AZURE_OPENAI: AzureOpenAIProvider,
    ProviderType.MISTRAL: MistralProvider,
    ProviderType.GROQ: GroqProvider,
    ProviderType.CUSTOM: CustomProvider,
}


class ModelRouter:
    """The Model Router — the single entry point for all LLM calls.

    Usage:
        router = ModelRouter()
        await router.register_provider(ProviderConfig(type=ProviderType.OPENAI, ...))
        response = await router.complete(ModelRequest(messages=[...]))
    """

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}
        self._configs: dict[str, ProviderConfig] = {}
        self._health: dict[str, ProviderHealthState] = {}
        self._cost_ledger = CostLedger()
        self._rate_limiter = RateLimiter()

    @property
    def cost_ledger(self) -> CostLedger:
        """Return the cost ledger."""
        return self._cost_ledger

    @property
    def rate_limiter(self) -> RateLimiter:
        """Return the rate limiter."""
        return self._rate_limiter

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    async def register_provider(self, config: ProviderConfig) -> str:
        """Register and initialize a provider.

        Returns the provider name.
        """
        cls = _PROVIDER_CLASSES.get(config.type)
        if cls is None:
            raise ValueError(f"Unknown provider type: {config.type}")

        provider = cls()
        await provider.initialize(config)
        self._providers[config.name] = provider
        self._configs[config.name] = config
        self._health[config.name] = ProviderHealthState(provider=config.name)
        self._rate_limiter.register_provider(
            config.name,
            max_requests_per_minute=config.max_requests_per_minute,
            max_tokens_per_minute=config.max_tokens_per_minute,
        )
        _log.info(
            "model_router.provider_registered",
            provider=config.name,
            type=config.type.value,
            priority=config.priority,
        )
        return config.name

    async def unregister_provider(self, name: str) -> bool:
        """Unregister a provider."""
        provider = self._providers.pop(name, None)
        if provider is None:
            return False
        await provider.shutdown()
        self._configs.pop(name, None)
        self._health.pop(name, None)
        _log.info("model_router.provider_unregistered", provider=name)
        return True

    def list_providers(self) -> list[ProviderHealth]:
        """Return health reports for all providers."""
        return [state.to_report() for state in self._health.values()]

    def get_provider_health(self, name: str) -> ProviderHealth | None:
        """Return the health report for a specific provider."""
        state = self._health.get(name)
        return state.to_report() if state else None

    async def list_models(self, provider: str | None = None) -> list[ModelInfo]:
        """Return all models (optionally filtered by provider)."""
        if provider is not None:
            p = self._providers.get(provider)
            if p is None:
                return []
            return await p.list_models()
        result: list[ModelInfo] = []
        for p in self._providers.values():
            result.extend(await p.list_models())
        return result

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete a request. Handles provider selection, failover, cost tracking."""
        providers = self._select_providers(request)
        if not providers:
            raise ProviderError("router", "No providers available")

        last_error: Exception | None = None
        for provider_name in providers:
            provider = self._providers[provider_name]
            health = self._health[provider_name]
            if health.status == ProviderStatus.UNHEALTHY:
                continue

            # Check rate limit
            if not self._rate_limiter.can_request(provider_name):
                _log.info("model_router.rate_limited", provider=provider_name)
                continue

            try:
                start = time.monotonic()
                response = await provider.complete(request)
                latency = time.monotonic() - start
                health.record_success(latency)
                self._rate_limiter.record_request(
                    provider_name,
                    response.usage.total_tokens,
                )
                # Record cost
                await self._cost_ledger.record(
                    provider=provider_name,
                    model=response.model,
                    cost_usd=response.cost_usd,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )
                return response
            except RateLimitError as e:
                health.record_failure(str(e))
                _log.warning("model_router.rate_limit_error", provider=provider_name)
                last_error = e
                continue
            except ProviderError as e:
                health.record_failure(str(e))
                if not e.retryable:
                    raise
                _log.warning(
                    "model_router.provider_error",
                    provider=provider_name,
                    error=str(e),
                    retryable=e.retryable,
                )
                last_error = e
                continue
            except Exception as e:
                health.record_failure(str(e))
                _log.exception("model_router.unexpected_error", provider=provider_name)
                last_error = e
                continue

        raise ProviderError(
            "router",
            f"All providers failed. Last error: {last_error}",
            retryable=False,
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        """Stream a request. Handles provider selection and failover.

        Note: if the streaming provider fails mid-stream, failover is NOT
        possible (the caller has already received partial output). The error
        is propagated.
        """
        request.hints.add(RequestHint.STREAMING)
        providers = self._select_providers(request)
        if not providers:
            raise ProviderError("router", "No providers available")

        for provider_name in providers:
            provider = self._providers[provider_name]
            health = self._health[provider_name]
            if health.status == ProviderStatus.UNHEALTHY:
                continue
            if not self._rate_limiter.can_request(provider_name):
                continue

            try:
                start = time.monotonic()
                async for chunk in provider.stream(request):
                    yield chunk
                latency = time.monotonic() - start
                health.record_success(latency)
                return
            except (RateLimitError, ProviderError) as e:
                health.record_failure(str(e))
                _log.warning("model_router.stream_error", provider=provider_name, error=str(e))
                continue
            except Exception as e:
                health.record_failure(str(e))
                _log.exception("model_router.stream_unexpected_error", provider=provider_name)
                continue

        raise ProviderError("router", "All providers failed for streaming")

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------

    def _select_providers(self, request: ModelRequest) -> list[str]:
        """Select and rank providers for this request.

        Returns a list of provider names, highest-priority first.
        """
        candidates: list[tuple[int, str]] = []

        for name, config in self._configs.items():
            if not config.enabled:
                continue
            health = self._health[name]
            if health.status == ProviderStatus.UNHEALTHY:
                continue

            # If provider_hint is set, only consider that provider
            if request.provider_hint and name != request.provider_hint:
                continue

            # If model_hint is set, we accept all providers and let the
            # provider fail if the model is invalid. A future optimization
            # would cache the model list and filter here.
            candidates.append((config.priority, name))

        # Sort by priority (1 = highest)
        candidates.sort(key=lambda c: c[0])
        return [name for _, name in candidates]

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def health_check_all(self) -> dict[str, ProviderHealth]:
        """Run health checks on all providers."""
        results: dict[str, ProviderHealth] = {}
        for name, provider in self._providers.items():
            try:
                health = await provider.health_check()
                results[name] = health
            except Exception as e:
                results[name] = ProviderHealth(
                    provider=name,
                    status=ProviderStatus.UNHEALTHY,
                    last_error=str(e),
                )
        return results

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Shut down all providers."""
        for provider in self._providers.values():
            try:
                await provider.shutdown()
            except Exception:
                _log.exception("model_router.shutdown_failed")
        self._providers.clear()
        self._configs.clear()
        self._health.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: ModelRouter | None = None


def init_model_router() -> ModelRouter:
    """Initialize the global Model Router."""
    global _INSTANCE
    _INSTANCE = ModelRouter()
    return _INSTANCE


def get_model_router() -> ModelRouter:
    """Return the global Model Router."""
    if _INSTANCE is None:
        raise RuntimeError("ModelRouter not initialized. Call init_model_router() first.")
    return _INSTANCE


def set_model_router(router: ModelRouter) -> None:
    """Set the global Model Router (for testing)."""
    global _INSTANCE
    _INSTANCE = router
