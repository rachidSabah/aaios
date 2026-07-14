"""ModelProvider Protocol + ProviderConfig + provider exceptions.

Every provider adapter implements the ModelProvider Protocol. The Model
Router holds a registry of providers and routes requests to them based on
health, cost, priority, and hints.

13 providers (Phase 6):
  OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA, Ollama,
  LM Studio, Azure OpenAI, Mistral, Groq, Custom

10 of these are OpenAI-compatible (share the OpenAI API format):
  OpenAI, Azure OpenAI, OpenRouter, DeepSeek, GLM, NVIDIA, Groq, Mistral,
  LM Studio, Custom

3 have their own SDKs: Anthropic, Google, Ollama (though Ollama also
exposes an OpenAI-compatible endpoint, which we use).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from core.contracts.model.health import ProviderHealth, ProviderStatus
from core.contracts.model.request import ModelRequest
from core.contracts.model.response import ModelResponse, ModelStreamChunk

__all__ = [
    "ModelInfo",
    "ModelProvider",
    "ProviderConfig",
    "ProviderError",
    "ProviderHealthState",
    "ProviderType",
    "RateLimitError",
]


class ProviderType(StrEnum):
    """The 13 supported provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    GLM = "glm"
    NVIDIA = "nvidia"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    AZURE_OPENAI = "azure_openai"
    MISTRAL = "mistral"
    GROQ = "groq"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """Configuration for a single provider.

    Secrets (api_key) are stored as SecretStr — they're never logged.
    The actual value is retrieved via ``api_key.get_secret_value()`` only
    at the point of use.
    """

    model_config = ConfigDict(extra="forbid")

    type: ProviderType
    name: str = Field(description='Display name, e.g. "OpenAI".')
    enabled: bool = Field(default=True)
    priority: int = Field(default=10, ge=1, description="1 = highest priority.")
    api_key: SecretStr | None = Field(default=None, description="API key (encrypted at rest).")
    base_url: str | None = Field(default=None, description="Override the default API endpoint.")
    # Per-provider model list (None = use the provider's default list)
    models: list[str] | None = None
    # Rate limiting
    max_requests_per_minute: int = Field(default=60, ge=1)
    max_tokens_per_minute: int = Field(default=100_000, ge=1)
    # Health monitoring
    health_check_interval_s: int = Field(default=60, ge=1)
    # Cost tracking
    cost_per_1m_input_usd: float = Field(default=0.0, ge=0.0)
    cost_per_1m_output_usd: float = Field(default=0.0, ge=0.0)
    # Failover
    max_retries: int = Field(default=2, ge=0)
    timeout_s: float = Field(default=120.0, ge=1.0)
    # Extra provider-specific config
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    """Information about a specific model offered by a provider."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description='Model ID, e.g. "gpt-4o-2024-08-06".')
    display_name: str = Field(default="")
    provider: str = Field(description="Provider name.")
    # Capabilities
    supports_streaming: bool = Field(default=True)
    supports_tools: bool = Field(default=True)
    supports_vision: bool = Field(default=False)
    supports_reasoning: bool = Field(default=False)
    supports_caching: bool = Field(default=False)
    # Context window
    context_window: int = Field(default=8192, ge=1)
    max_output_tokens: int = Field(default=4096, ge=1)
    # Cost (per 1M tokens)
    cost_per_1m_input_usd: float = Field(default=0.0, ge=0.0)
    cost_per_1m_output_usd: float = Field(default=0.0, ge=0.0)
    # Reasoning cost (for o1-style models)
    cost_per_1m_reasoning_usd: float = Field(default=0.0, ge=0.0)


class ProviderHealthState(BaseModel):
    """Mutable health state for a provider (tracked by the health monitor)."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    recent_latencies: list[float] = Field(
        default_factory=list, description="Last 100 latencies (seconds)."
    )
    last_error: str | None = None

    def record_success(self, latency_s: float) -> None:
        """Record a successful request."""
        self.consecutive_failures = 0
        self.total_requests += 1
        self.recent_latencies.append(latency_s)
        if len(self.recent_latencies) > 100:
            self.recent_latencies = self.recent_latencies[-100:]
        if self.status == ProviderStatus.UNHEALTHY:
            self.status = ProviderStatus.HEALTHY

    def record_failure(self, error: str) -> None:
        """Record a failed request."""
        self.consecutive_failures += 1
        self.total_requests += 1
        self.total_failures += 1
        self.last_error = error
        if self.consecutive_failures >= 5:
            self.status = ProviderStatus.UNHEALTHY
        elif self.consecutive_failures >= 2:
            self.status = ProviderStatus.DEGRADED

    def to_report(self) -> ProviderHealth:
        """Convert to an immutable ProviderHealth report."""
        import statistics

        latencies = self.recent_latencies
        avg = statistics.mean(latencies) if latencies else 0.0
        p95 = (
            statistics.quantiles(latencies, n=20)[18]
            if len(latencies) >= 20
            else (max(latencies) if latencies else 0.0)
        )
        success_rate = 1.0 - (self.total_failures / max(1, self.total_requests))
        return ProviderHealth(
            provider=self.provider,
            status=self.status,
            success_rate=success_rate,
            avg_latency_s=avg,
            p95_latency_s=p95,
            consecutive_failures=self.consecutive_failures,
            last_error=self.last_error,
        )


@runtime_checkable
class ModelProvider(Protocol):
    """The interface every provider adapter implements.

    The Model Router calls these methods. Each provider translates between
    the universal ModelRequest/ModelResponse format and its native API.
    """

    @property
    def name(self) -> str:
        """Return the provider name (e.g. 'openai')."""
        ...

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    async def initialize(self, config: ProviderConfig) -> None:
        """Initialize the provider with configuration."""
        ...

    async def shutdown(self) -> None:
        """Release resources."""
        ...

    async def list_models(self) -> list[ModelInfo]:
        """Return the models this provider offers."""
        ...

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete a request (non-streaming)."""
        ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamChunk]:
        """Stream a request. Yields chunks; the last chunk has usage + finish_reason."""
        ...

    async def health_check(self) -> ProviderHealth:
        """Probe the provider's health."""
        ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProviderError(RuntimeError):
    """Base class for provider errors."""

    def __init__(self, provider: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.retryable = retryable


class RateLimitError(ProviderError):
    """Raised when a provider returns a rate-limit error (429)."""

    def __init__(self, provider: str, retry_after_s: float = 60.0) -> None:
        super().__init__(provider, f"Rate limited (retry after {retry_after_s}s)", retryable=True)
        self.retry_after_s = retry_after_s
