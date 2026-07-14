"""GLM (Zhipu) provider — OpenAI-compatible."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class GLMProvider(OpenAICompatibleProvider):
    """GLM (Zhipu) provider."""

    _provider_type = ProviderType.GLM
    _default_base_url = "https://open.bigmodel.cn/api/paas/v4"

    _model_catalog: dict[str, ModelInfo] = {
        "glm-4-plus": ModelInfo(
            name="glm-4-plus",
            display_name="GLM-4-Plus",
            provider="glm",
            supports_tools=True,
            supports_vision=True,
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=0.70,
            cost_per_1m_output_usd=2.10,
        ),
        "glm-4-flash": ModelInfo(
            name="glm-4-flash",
            display_name="GLM-4-Flash (free)",
            provider="glm",
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1m_input_usd=0.0,
            cost_per_1m_output_usd=0.0,
        ),
    }
