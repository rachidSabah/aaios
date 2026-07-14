"""ModelRequest — the universal request format for LLM calls."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.model.message import ModelMessage
from core.contracts.model.tools import ToolDefinition

__all__ = ["ModelRequest", "RequestHint"]


class RequestHint(StrEnum):
    """Hints to the Model Router for provider/model selection.

    The router uses these to pick the best provider + model. They are
    hints, not requirements — the router may override based on health,
    cost, or configuration.
    """

    CHEAP = "cheap"  # prefer the cheapest model that can do the job
    FAST = "fast"  # prefer the lowest-latency model
    SMART = "smart"  # prefer the highest-quality model
    REASONING = "reasoning"  # prefer a reasoning model (o1, Claude Thinking, etc.)
    VISION = "vision"  # requires vision capability
    STREAMING = "streaming"  # caller wants streaming output


class ModelRequest(BaseModel):
    """A request to the Model Router.

    Agents construct this and call ``router.complete(request)`` or
    ``router.stream(request)``. The router picks the provider + model,
    handles failover, tracks cost, and returns the response.

    The ``model_hint`` is a suggestion (e.g. 'gpt-4o', 'claude-3-5-sonnet').
    If None, the router picks based on ``hints`` and the configured priority.
    If the hinted model is unavailable, the router falls back to the next
    priority provider.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="Unique request ID.")
    messages: list[ModelMessage] = Field(min_length=1)
    model_hint: str | None = Field(
        default=None,
        description='Preferred model (e.g. "gpt-4o"). None = router picks.',
    )
    provider_hint: str | None = Field(
        default=None,
        description='Preferred provider (e.g. "openai"). None = router picks.',
    )
    hints: set[RequestHint] = Field(default_factory=set)
    # Generation parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stop: list[str] | None = None
    # Tool calling
    tools: list[ToolDefinition] | None = None
    tool_choice: str | None = Field(
        default=None,
        description='"auto", "none", "required", or a specific tool name.',
    )
    # Context caching (Anthropic prompt caching, OpenAI implicit caching)
    cache_key: str | None = Field(
        default=None,
        description="If set, the router attempts to cache the prefix.",
    )
    # Cost tracking
    max_cost_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="If set, the request fails if the estimated cost exceeds this.",
    )
    # Metadata for logging/telemetry
    metadata: dict[str, Any] = Field(default_factory=dict)
