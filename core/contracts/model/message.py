"""Chat messages — the universal message format for all LLM providers.

Every provider adapter converts between this format and its native API format.
This keeps the rest of the system provider-agnostic.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ModelMessage", "ModelRole"]


class ModelRole(StrEnum):
    """The role of a message in a chat conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"  # tool call result


class ModelMessage(BaseModel):
    """A single chat message.

    For text-only messages, use ``content`` (str).
    For multimodal (vision), use ``content`` as a list of parts:
        [{'type': 'text', 'text': 'What is this?'},
         {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,...'}}]

    For tool calls (assistant role), use ``tool_calls``.
    For tool results (tool role), use ``tool_call_id`` + ``content``.
    """

    model_config = ConfigDict(extra="forbid")

    role: ModelRole
    content: str | list[dict[str, Any]] = Field(default="")
    name: str | None = Field(default=None, description="Optional name (for tool role).")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None,
        description="Tool calls made by the assistant.",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="The tool call ID this message responds to (for tool role).",
    )

    @classmethod
    def system(cls, content: str) -> ModelMessage:
        """Create a system message."""
        return cls(role=ModelRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> ModelMessage:
        """Create a user message."""
        return cls(role=ModelRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> ModelMessage:
        """Create an assistant message."""
        return cls(role=ModelRole.ASSISTANT, content=content)

    @classmethod
    def tool(cls, tool_call_id: str, content: str) -> ModelMessage:
        """Create a tool result message."""
        return cls(role=ModelRole.TOOL, content=content, tool_call_id=tool_call_id)
