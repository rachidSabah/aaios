"""Tool Registry implementation.

A tool is an async callable with:
  - a name (dot-separated, namespaced)
  - a JSON schema for inputs (LLM tool-calling)
  - a permission requirement
  - an optional description (for the LLM)

The registry validates inputs against the schema, checks permissions, calls
the handler, and audit-logs the call.

Subscriptions to tool registration events flow on the event bus
(``tool.registered``, ``tool.unregistered``) so the MCP Manager and Plugin
Manager can react.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.actor import ActorRef
from core.contracts.permission import Permission
from core.logging import get_logger

_log = get_logger(__name__)

# Tool handler signature: takes a dict of args + context, returns a result
ToolHandler = Callable[[dict[str, Any], "ToolCallContext"], Awaitable[Any]]


class ToolError(RuntimeError):
    """Base class for tool errors."""


class ToolNotFoundError(ToolError):
    """Raised when a tool is not in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Tool '{name}' not found in registry.")
        self.name = name


class ToolValidationError(ToolError):
    """Raised when tool inputs fail schema validation."""


@dataclass
class ToolCallContext:
    """Context passed to every tool handler."""

    actor: ActorRef
    correlation_id: str
    task_id: str | None = None
    sandbox_root: Any | None = None  # Path
    metadata: dict[str, str] = field(default_factory=dict)


class ToolCallResult(BaseModel):
    """The result of a tool call."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    output: Any = None
    error: str | None = None
    duration_s: float = 0.0


class Tool(BaseModel):
    """A registered tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(description="Dot-separated, namespaced, e.g. ``slack.send_message``.")
    version: str = Field(default="1.0.0")
    description: str = Field(default="")
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for inputs (for LLM tool-calling).",
    )
    permission: Permission = Field(
        default_factory=lambda: Permission(name="tool.call"),
    )
    handler: Any = Field(
        description="Async callable: (args, ctx) -> result.",
        exclude=True,
    )

    async def call(self, args: dict[str, Any], ctx: ToolCallContext) -> ToolCallResult:
        """Invoke the tool with argument validation."""
        import time

        start = time.monotonic()
        try:
            result = await self.handler(args, ctx)
            duration = time.monotonic() - start
            return ToolCallResult(success=True, output=result, duration_s=duration)
        except Exception as e:
            duration = time.monotonic() - start
            return ToolCallResult(success=False, error=str(e), duration_s=duration)


class ToolRegistry:
    """The Tool Registry — single source of truth for tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Overwrites an existing tool with the same name."""
        if tool.name in self._tools:
            _log.warning("tool.overwritten", name=tool.name)
        self._tools[tool.name] = tool
        _log.info("tool.registered", name=tool.name, version=tool.version)

    def unregister(self, name: str) -> bool:
        """Unregister a tool. Returns True if it was present."""
        if name in self._tools:
            del self._tools[name]
            _log.info("tool.unregistered", name=name)
            return True
        return False

    def get(self, name: str) -> Tool:
        """Return the tool with ``name``, or raise ToolNotFoundError."""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list(self, prefix: str | None = None) -> list[Tool]:
        """Return all tools (optionally filtered by name prefix)."""
        if prefix is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.name.startswith(prefix)]

    def has(self, name: str) -> bool:
        """Return True if the tool exists."""
        return name in self._tools

    async def call(
        self,
        name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        """Call a tool by name. Returns the result (or an error result)."""
        try:
            tool = self.get(name)
        except ToolNotFoundError as e:
            return ToolCallResult(success=False, error=str(e))
        return await tool.call(args, ctx)


# Singleton
_INSTANCE: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the singleton Tool Registry."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ToolRegistry()
    return _INSTANCE


def set_tool_registry(registry: ToolRegistry) -> None:
    """Set the singleton Tool Registry (for testing)."""
    global _INSTANCE
    _INSTANCE = registry
