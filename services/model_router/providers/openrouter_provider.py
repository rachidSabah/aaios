"""OpenRouter provider — access 100+ models through one API."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderConfig, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter provider — aggregates many providers behind one API."""

    _provider_type = ProviderType.OPENROUTER
    _default_base_url = "https://openrouter.ai/api/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "openai/gpt-4o": ModelInfo(
            name="openai/gpt-4o",
            display_name="GPT-4o (via OpenRouter)",
            provider="openrouter",
            supports_vision=True,
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=16_384,
            cost_per_1m_input_usd=2.50,
            cost_per_1m_output_usd=10.00,
        ),
        "anthropic/claude-3.5-sonnet": ModelInfo(
            name="anthropic/claude-3.5-sonnet",
            display_name="Claude 3.5 Sonnet (via OpenRouter)",
            provider="openrouter",
            supports_vision=True,
            supports_tools=True,
            context_window=200_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=3.00,
            cost_per_1m_output_usd=15.00,
        ),
        "google/gemini-pro-1.5": ModelInfo(
            name="google/gemini-pro-1.5",
            display_name="Gemini Pro 1.5 (via OpenRouter)",
            provider="openrouter",
            supports_vision=True,
            supports_tools=True,
            context_window=2_000_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=1.25,
            cost_per_1m_output_usd=5.00,
        ),
    }

    async def initialize(self, config: ProviderConfig) -> None:
        """Initialize with OpenRouter-specific headers."""
        if not config.extra.get("headers"):
            config.extra["headers"] = {}
        config.extra["headers"].setdefault("HTTP-Referer", "https://github.com/rachidSabah/aaios")
        config.extra["headers"].setdefault("X-Title", "AAiOS")
        await super().initialize(config)
