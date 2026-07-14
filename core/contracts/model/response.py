"""ModelResponse + ModelStreamChunk + UsageStats."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.model.tools import ToolCall
from core.contracts.timestamp import utc_now

__all__ = ["ModelResponse", "ModelStreamChunk", "UsageStats"]


class UsageStats(BaseModel):
    """Token usage statistics returned by the provider."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    # For providers that support it (Anthropic prompt caching)
    cached_tokens: int = Field(default=0, ge=0)
    # Reasoning tokens (for o1-style models)
    reasoning_tokens: int = Field(default=0, ge=0)


class ModelResponse(BaseModel):
    """The response from a model completion."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(description="The ModelRequest ID.")
    provider: str = Field(description="Which provider handled the request.")
    model: str = Field(description='Which model was used (e.g. "gpt-4o-2024-08-06").')
    content: str = Field(default="", description="The generated text.")
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: UsageStats = Field(default_factory=UsageStats)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_s: float = Field(default=0.0, ge=0.0)
    finish_reason: str = Field(
        default="stop",
        description='"stop", "length", "tool_calls", or "content_filter".',
    )
    completed_at: datetime = Field(default_factory=utc_now)
    # Raw provider response (for debugging; not for programmatic use)
    raw: dict[str, Any] | None = Field(default=None, exclude=True)


class ModelStreamChunk(BaseModel):
    """A single chunk from a streaming response."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    provider: str
    model: str
    # Incremental content (may be empty for the first/last chunk)
    content_delta: str = Field(default="")
    # Tool call deltas (streaming)
    tool_call_deltas: list[dict[str, Any]] = Field(default_factory=list)
    # Present only on the final chunk
    usage: UsageStats | None = None
    finish_reason: str | None = None
