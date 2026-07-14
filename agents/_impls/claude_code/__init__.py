"""Claude Code CodingAgent — one implementation of the CodingAgent type.

A subprocess bridge that wraps a coding CLI via JSON-RPC. Satisfies both
the GenericAgent Protocol (11 methods) and the CodingAgent Protocol
(read_file, write_file, run_tests, git, shell, review).

If no real CLI binary is available, the agent runs in "mock mode" — it
returns canned responses for testing.
"""

from __future__ import annotations

from agents._impls.claude_code.agent import ClaudeCodeCodingAgent
from agents._impls.claude_code.capabilities import build_manifest
from agents._impls.claude_code.protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    RPCErrorCode,
)
from agents._impls.claude_code.sandbox import FilesystemSandbox, SandboxViolationError

__all__ = [
    "ClaudeCodeCodingAgent",
    "FilesystemSandbox",
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "RPCErrorCode",
    "SandboxViolationError",
    "build_manifest",
]
