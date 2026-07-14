"""DeepSeek provider — OpenAI-compatible."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek provider."""

    _provider_type = ProviderType.DEEPSEEK
    _default_base_url = "https://api.deepseek.com/v1"

    _model_catalog: dict[str, ModelInfo] = {
        "deepseek-chat": ModelInfo(
            name="deepseek-chat",
            display_name="DeepSeek Chat",
            provider="deepseek",
            supports_tools=True,
            supports_streaming=True,
            context_window=64_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=0.14,
            cost_per_1m_output_usd=0.28,
        ),
        "deepseek-reasoner": ModelInfo(
            name="deepseek-reasoner",
            display_name="DeepSeek Reasoner (R1)",
            provider="deepseek",
            supports_reasoning=True,
            supports_tools=True,
            supports_streaming=True,
            context_window=64_000,
            max_output_tokens=8_192,
            cost_per_1m_input_usd=0.55,
            cost_per_1m_output_usd=2.19,
        ),
    }
