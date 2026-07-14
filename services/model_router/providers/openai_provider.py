"""OpenAI provider — the canonical OpenAI-compatible provider.

Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o1-mini, o3-mini, etc.
"""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI provider."""

    _provider_type = ProviderType.OPENAI
    _default_base_url = "https://api.openai.com/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "gpt-4o": ModelInfo(
            name="gpt-4o",
            display_name="GPT-4o",
            provider="openai",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=128_000,
            max_output_tokens=16_384,
            cost_per_1m_input_usd=2.50,
            cost_per_1m_output_usd=10.00,
        ),
        "gpt-4o-mini": ModelInfo(
            name="gpt-4o-mini",
            display_name="GPT-4o mini",
            provider="openai",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=128_000,
            max_output_tokens=16_384,
            cost_per_1m_input_usd=0.15,
            cost_per_1m_output_usd=0.60,
        ),
        "gpt-4-turbo": ModelInfo(
            name="gpt-4-turbo",
            display_name="GPT-4 Turbo",
            provider="openai",
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=10.00,
            cost_per_1m_output_usd=30.00,
        ),
        "o1": ModelInfo(
            name="o1",
            display_name="o1",
            provider="openai",
            supports_reasoning=True,
            supports_tools=False,
            supports_streaming=False,
            context_window=200_000,
            max_output_tokens=100_000,
            cost_per_1m_input_usd=15.00,
            cost_per_1m_output_usd=60.00,
        ),
        "o1-mini": ModelInfo(
            name="o1-mini",
            display_name="o1-mini",
            provider="openai",
            supports_reasoning=True,
            supports_tools=False,
            supports_streaming=False,
            context_window=128_000,
            max_output_tokens=65_536,
            cost_per_1m_input_usd=3.00,
            cost_per_1m_output_usd=12.00,
        ),
        "o3-mini": ModelInfo(
            name="o3-mini",
            display_name="o3-mini",
            provider="openai",
            supports_reasoning=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=200_000,
            max_output_tokens=100_000,
            cost_per_1m_input_usd=1.10,
            cost_per_1m_output_usd=4.40,
        ),
    }
