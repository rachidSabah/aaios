"""Tool calling contracts — for LLM function/tool calling."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ToolCall", "ToolCallResult", "ToolDefinition"]


class ToolDefinition(BaseModel):
    """A tool the LLM can call.

    Uses JSON Schema for the parameters, matching the OpenAI/Anthropic
    tool-calling format. The router converts this to the provider's native
    format if needed.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = Field(default="")
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema for the tool parameters.",
    )


class ToolCall(BaseModel):
    """A tool call made by the LLM."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique call ID (provider-assigned).")
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    """The result of executing a tool call."""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    result: Any = Field(description="The tool output (will be JSON-serialized).")
    is_error: bool = Field(default=False)
