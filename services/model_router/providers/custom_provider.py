"""Custom OpenAI-compatible provider — for any provider not in the built-in list."""

from __future__ import annotations

from core.contracts.provider import ModelInfo, ProviderType
from services.model_router.providers.openai_compatible import OpenAICompatibleProvider


class CustomProvider(OpenAICompatibleProvider):
    """Custom OpenAI-compatible provider.

    The user must set ``base_url`` and optionally ``models`` in the ProviderConfig.
    No model catalog — models are whatever the user configures.
    """

    _provider_type = ProviderType.CUSTOM
    _default_base_url = ""  # must be set in config

    _model_catalog: dict[str, ModelInfo] = {}
