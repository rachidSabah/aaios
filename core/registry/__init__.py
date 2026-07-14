"""Registry package — Tool Registry + Prompt Registry."""

from __future__ import annotations

from core.registry.prompt_registry import (
    Prompt,
    PromptError,
    PromptNotFoundError,
    PromptRegistry,
    PromptRenderError,
    get_prompt_registry,
    set_prompt_registry,
)
from core.registry.tool_registry import (
    Tool,
    ToolCallContext,
    ToolCallResult,
    ToolError,
    ToolNotFoundError,
    ToolRegistry,
    get_tool_registry,
    set_tool_registry,
)

__all__ = [
    "Prompt",
    "PromptError",
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptRenderError",
    "Tool",
    "ToolCallContext",
    "ToolCallResult",
    "ToolError",
    "ToolNotFoundError",
    "ToolRegistry",
    "get_prompt_registry",
    "get_tool_registry",
    "set_prompt_registry",
    "set_tool_registry",
]
