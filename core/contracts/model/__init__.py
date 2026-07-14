"""Model Router contracts — ModelRequest, ModelResponse, ModelProvider Protocol.

These contracts are L1 (kernel) — they live in ``core/contracts/model/``
because the Model Router (L2), agents (L3), and the Supervisor (L4) all
need them.

Key principle: agents never call providers directly. They construct a
ModelRequest and hand it to the Model Router, which picks the provider,
handles failover, tracks cost, and returns a ModelResponse.
"""

from __future__ import annotations

from core.contracts.model.health import ProviderHealth, ProviderStatus
from core.contracts.model.message import ModelMessage, ModelRole
from core.contracts.model.request import ModelRequest
from core.contracts.model.response import ModelResponse, ModelStreamChunk, UsageStats
from core.contracts.model.tools import ToolCall, ToolCallResult, ToolDefinition
from core.contracts.provider import (
    ModelInfo,
    ModelProvider,
    ProviderConfig,
    ProviderError,
    ProviderHealthState,
    ProviderType,
    RateLimitError,
)

__all__ = [
    "ModelInfo",
    "ModelMessage",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "ModelRole",
    "ModelStreamChunk",
    "ProviderConfig",
    "ProviderError",
    "ProviderHealth",
    "ProviderHealthState",
    "ProviderStatus",
    "ProviderType",
    "RateLimitError",
    "ToolCall",
    "ToolCallResult",
    "ToolDefinition",
    "UsageStats",
]
