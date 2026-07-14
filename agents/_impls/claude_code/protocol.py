"""JSON-RPC protocol for the Claude Code subprocess bridge.

The bridge communicates with the `claude` CLI over stdin/stdout using
newline-delimited JSON-RPC 2.0 messages. Each message is a single JSON
object on one line.

Protocol:
  - Request:  {"jsonrpc": "2.0", "id": <uuid>, "method": <string>, "params": {...}}
  - Response: {"jsonrpc": "2.0", "id": <uuid>, "result": <any>} or
              {"jsonrpc": "2.0", "id": <uuid>, "error": {"code": <int>, "message": <string>}}
  - Notification (no response): {"jsonrpc": "2.0", "method": <string>, "params": {...}}

Methods:
  - initialize: handshake (returns agent identity + capabilities)
  - execute_task: execute a task (returns TaskResult)
  - cancel_task: cancel an in-flight task
  - shutdown: graceful shutdown
  - health_check: return health status
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "JSONRPCError",
    "JSONRPCNotification",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "RPCErrorCode",
]


class RPCErrorCode:
    """JSON-RPC error codes (standard + custom)."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Custom codes (application-level)
    TASK_FAILED = -32000
    TASK_CANCELLED = -32001
    SANDBOX_VIOLATION = -32002
    PERMISSION_DENIED = -32003


class JSONRPCRequest(BaseModel):
    """A JSON-RPC 2.0 request."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = Field(default="2.0")
    id: str = Field(default_factory=lambda: str(uuid4()))
    method: str
    params: dict[str, Any] = Field(default_factory=dict)

    def to_line(self) -> str:
        """Serialize to a newline-delimited JSON string."""
        return json.dumps(self.model_dump()) + "\n"

    @classmethod
    def from_line(cls, line: str) -> JSONRPCRequest:
        """Parse from a JSON line."""
        return cls.model_validate_json(line.strip())


class JSONRPCResponse(BaseModel):
    """A JSON-RPC 2.0 response (result OR error, never both)."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = Field(default="2.0")
    id: str
    result: Any | None = None
    error: dict[str, Any] | None = None

    def to_line(self) -> str:
        """Serialize to a newline-delimited JSON string."""
        return json.dumps(self.model_dump(exclude_none=True)) + "\n"

    @classmethod
    def from_line(cls, line: str) -> JSONRPCResponse:
        """Parse from a JSON line."""
        return cls.model_validate_json(line.strip())

    @property
    def is_error(self) -> bool:
        """Return True if this is an error response."""
        return self.error is not None

    @classmethod
    def success(cls, id: str, result: Any) -> JSONRPCResponse:
        """Create a success response."""
        return cls(jsonrpc="2.0", id=id, result=result)

    @classmethod
    def error_response(cls, id: str, code: int, message: str, data: Any = None) -> JSONRPCResponse:
        """Create an error response."""
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return cls(jsonrpc="2.0", id=id, error=error)


class JSONRPCNotification(BaseModel):
    """A JSON-RPC 2.0 notification (no response expected)."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: str = Field(default="2.0")
    method: str
    params: dict[str, Any] = Field(default_factory=dict)

    def to_line(self) -> str:
        """Serialize to a newline-delimited JSON string."""
        return json.dumps(self.model_dump()) + "\n"


class JSONRPCError(RuntimeError):
    """Raised when a JSON-RPC response contains an error."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data
