"""Mistral provider — OpenAI-compatible."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class MistralProvider(OpenAICompatibleProvider):
    """Mistral provider."""

    _provider_type = ProviderType.MISTRAL
    _default_base_url = "https://api.mistral.ai/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "mistral-large-latest": ModelInfo(
            name="mistral-large-latest",
            display_name="Mistral Large",
            provider="mistral",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=2.00,
            cost_per_1m_output_usd=6.00,
        ),
        "mistral-small-latest": ModelInfo(
            name="mistral-small-latest",
            display_name="Mistral Small",
            provider="mistral",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.20,
            cost_per_1m_output_usd=0.60,
        ),
    }
