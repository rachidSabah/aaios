"""Azure OpenAI provider — OpenAI-compatible with a different URL structure."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """Azure OpenAI provider.

    Requires ``extra['azure_endpoint']`` and ``extra['api_version']`` in the
    ProviderConfig. The base URL is constructed as:
        ``{azure_endpoint}/openai/deployments/{deployment}``
    """

    _provider_type = ProviderType.AZURE_OPENAI
    _default_base_url = ""  # set from config.extra

    _model_catalog: dict[str, ModelInfo] = {
        "gpt-4o": ModelInfo(
            name="gpt-4o",
            display_name="GPT-4o (Azure)",
            provider="azure_openai",
            supports_vision=True,
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=16_384,
            cost_per_1m_input_usd=2.50,
            cost_per_1m_output_usd=10.00,
        ),
        "gpt-4o-mini": ModelInfo(
            name="gpt-4o-mini",
            display_name="GPT-4o mini (Azure)",
            provider="azure_openai",
            supports_vision=True,
            supports_tools=True,
            context_window=128_000,
            max_output_tokens=16_384,
            cost_per_1m_input_usd=0.15,
            cost_per_1m_output_usd=0.60,
        ),
    }
