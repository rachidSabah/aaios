"""Model Router — the centralized LLM access layer.

Agents never call providers directly. They construct a ModelRequest and
call ``router.complete(request)`` or ``router.stream(request)``. The router
handles provider selection, failover, cost tracking, rate limiting, and
health monitoring.

13 providers: OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA,
Ollama, LM Studio, Azure OpenAI, Mistral, Groq, Custom.
"""

from __future__ import annotations

from services.model_router.cost_ledger import CostEntry, CostLedger
from services.model_router.providers import (
    AnthropicProvider,
    AzureOpenAIProvider,
    CustomProvider,
    DeepSeekProvider,
    GLMProvider,
    GoogleProvider,
    GroqProvider,
    LMStudioProvider,
    MistralProvider,
    NVIDIAProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from services.model_router.rate_limiter import RateLimiter, RateLimitState
from services.model_router.router import (
    ModelRouter,
    get_model_router,
    init_model_router,
    set_model_router,
)

__all__ = [
    "AnthropicProvider",
    "AzureOpenAIProvider",
    "CostEntry",
    "CostLedger",
    "CustomProvider",
    "DeepSeekProvider",
    "GLMProvider",
    "GoogleProvider",
    "GroqProvider",
    "LMStudioProvider",
    "MistralProvider",
    "NVIDIAProvider",
    "ModelRouter",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "RateLimiter",
    "RateLimitState",
    "get_model_router",
    "init_model_router",
    "set_model_router",
]
