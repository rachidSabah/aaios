"""Claude Code CodingAgent — a CodingAgent implementation via subprocess bridge.

This agent wraps the official `claude` CLI (or any compatible coding agent
CLI) via a subprocess + JSON-RPC bridge. It satisfies:
  - The GenericAgent Protocol (11 methods)
  - The CodingAgent Protocol (read_file, write_file, run_tests, git, shell, review)

The agent spawns a subprocess, communicates via newline-delimited JSON-RPC
over stdin/stdout, and enforces a project-scoped filesystem sandbox.

If the `claude` CLI is not available, the agent falls back to a mock mode
that returns canned responses (useful for testing and development without
a real LLM subscription).
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from agents._base.subprocess_bridge import SubprocessBridgeAgent
from agents._impls.claude_code.capabilities import build_manifest
from agents._impls.claude_code.protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    RPCErrorCode,
)
from agents._impls.claude_code.sandbox import FilesystemSandbox
from core.contracts.agent import (
    AgentIdentity,
    AgentType,
    CapabilityManifest,
)
from core.contracts.health import HealthReport
from core.contracts.task import (
    TaskRequest,
    TaskResult,
    TaskResultStatus,
)
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["ClaudeCodeCodingAgent"]


class ClaudeCodeCodingAgent(SubprocessBridgeAgent):
    """A CodingAgent implementation that wraps a coding CLI via subprocess.

    The agent is identified as 'claude-code-v1' but the core architecture
    never references this name (INV-09). The Supervisor discovers it via
    the Agent Registry's capability index.

    If no real CLI binary is available, the agent runs in "mock mode" —
    it returns canned responses for testing.
    """

    def __init__(
        self,
        *,
        project_root: Path | str | None = None,
        cli_binary: str | None = None,
        mock_mode: bool = False,
        proxy_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        identity = AgentIdentity(
            agent_id="claude-code-v1",
            agent_type=AgentType.CODING,
            implementation_name="Claude Code",
            version="1.0.0",
            vendor="Anthropic",
        )
        super().__init__(identity)

        # Load agent config if available (written by bind_agents)
        agent_config = self._load_agent_config()
        if agent_config:
            cfg = agent_config.get("claude_code", {})
            if not cli_binary and cfg.get("binary_path"):
                cli_binary = cfg["binary_path"]
            if not mock_mode and cfg.get("mock_mode") is not None:
                mock_mode = cfg["mock_mode"]
            if not proxy_url and cfg.get("api_base_url"):
                proxy_url = cfg["api_base_url"]

        # Environment variable fallbacks
        if not proxy_url:
            proxy_url = os.environ.get("ANTHROPIC_BASE_URL")
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        self._cli_binary = cli_binary or self._find_cli_binary()
        self._mock_mode = mock_mode or (self._cli_binary is None)
        self._proxy_url = proxy_url
        self._api_key = api_key
        self._sandbox: FilesystemSandbox | None = None
        self._project_root: Path | None = None
        if project_root is not None:
            self._sandbox = FilesystemSandbox(project_root)
            self._project_root = self._sandbox.root
        self._manifest: CapabilityManifest = build_manifest()

    @staticmethod
    def _load_agent_config() -> dict[str, Any] | None:
        """Load agent configuration written by bind_agents.

        Checks:
        1. %ProgramData%/AAiOS/config/agents.json (Windows native)
        2. ~/.config/aaios/agents.json (Linux/WSL)
        3. ./config/agents.json (development)
        """
        import json

        candidates = [
            Path(os.environ.get("ProgramData", "/etc")) / "AAiOS" / "config" / "agents.json",
            Path.home() / ".config" / "aaios" / "agents.json",
            Path("config") / "agents.json",
        ]
        for path in candidates:
            if path.is_file():
                try:
                    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
                    return data
                except Exception:
                    pass
        return None

    @staticmethod
    def _find_cli_binary() -> str | None:
        """Try to find a coding CLI binary on PATH. Returns None if not found."""
        # The actual binary name is never referenced in core code (INV-09).
        # We search PATH for common coding agent CLIs.
        for name in ("claude",):
            path = os.environ.get("PATH", "")
            for directory in path.split(os.pathsep):
                full = Path(directory) / name
                if full.is_file():
                    return str(full)
        return None

    async def _on_initialize(self) -> None:
        """Initialize: spawn the subprocess (or enter mock mode)."""
        if self._mock_mode:
            _log.info("claude_code.mock_mode", agent_id=self._identity.agent_id)
            self._health = HealthReport.healthy()
            return

        # Real mode: spawn the CLI subprocess
        # The subprocess is spawned via the gateway (INV-02) — but for
        # Phase 9, we use asyncio.create_subprocess_exec directly since
        # the gateway.process.spawn() method is not yet implemented.
        # Phase 14 will route this through the gateway.
        assert self._cli_binary is not None
        try:
            # Build environment for the subprocess (includes proxy config)
            env = dict(os.environ)
            if self._proxy_url:
                env["ANTHROPIC_BASE_URL"] = self._proxy_url
                _log.info("claude_code.using_proxy", proxy_url=self._proxy_url)
            if self._api_key:
                env["ANTHROPIC_API_KEY"] = self._api_key

            self._process = await asyncio.create_subprocess_exec(
                self._cli_binary,
                "--json-rpc",  # enable JSON-RPC mode
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._project_root) if self._project_root else None,
                env=env,
            )
            _log.info(
                "claude_code.subprocess_started",
                agent_id=self._identity.agent_id,
                pid=self._process.pid,
                proxy=self._proxy_url or "official-api",
            )
            self._health = HealthReport.healthy()
        except Exception as e:
            _log.error("claude_code.subprocess_failed", error=str(e))
            self._health = HealthReport.unhealthy(str(e))
            raise

    async def _build_manifest(self) -> CapabilityManifest:
        """Return the capability manifest."""
        return self._manifest

    async def _rpc_call(self, method: str, params: dict[str, Any]) -> Any:
        """Send a JSON-RPC call and return the result.

        In mock mode, returns canned responses.
        """
        if self._mock_mode:
            return self._mock_rpc_call(method, params)

        if self._process is None or self._process.returncode is not None:
            raise RuntimeError("Subprocess not running")

        request = JSONRPCRequest(method=method, params=params)
        line = request.to_line()
        assert self._process.stdin is not None
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        # Read the response line
        assert self._process.stdout is not None
        response_line = await asyncio.wait_for(
            self._process.stdout.readline(),
            timeout=300.0,
        )
        if not response_line:
            raise RuntimeError("Subprocess closed unexpectedly")
        response = JSONRPCResponse.from_line(response_line.decode())
        if response.is_error:
            assert response.error is not None
            raise JSONRPCError(
                code=response.error.get("code", RPCErrorCode.INTERNAL_ERROR),
                message=response.error.get("message", "Unknown error"),
                data=response.error.get("data"),
            )
        return response.result

    def _mock_rpc_call(self, method: str, params: dict[str, Any]) -> Any:
        """Return canned responses for testing without a real CLI."""
        if method == "execute_task":
            goal = params.get("request", {}).get("goal", "")
            return TaskResult(
                task_id=params.get("request", {}).get("id", ""),
                status=TaskResultStatus.SUCCESS,
                output={"goal": goal, "result": "mock execution completed"},
                duration_s=0.01,
            ).model_dump()
        if method == "cancel_task":
            return {"cancelled": True}
        if method == "health_check":
            return {"status": "healthy"}
        return {"mock": True, "method": method}

    async def _execute(self, request: TaskRequest) -> TaskResult:
        """Execute a task via the subprocess bridge."""
        start = time.monotonic()
        try:
            result = await self._rpc_call(
                "execute_task",
                {
                    "request": request.model_dump(mode="json"),
                    "sandbox_root": str(self._project_root) if self._project_root else None,
                },
            )
            if isinstance(result, dict):
                result["duration_s"] = time.monotonic() - start
                return TaskResult(**result)
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.SUCCESS,
                output=result,
                duration_s=time.monotonic() - start,
            )
        except JSONRPCError as e:
            return TaskResult(
                task_id=request.id,
                status=TaskResultStatus.FAILURE,
                error=str(e),
                duration_s=time.monotonic() - start,
            )

    # ------------------------------------------------------------------
    # CodingAgent Protocol methods (type-specific convenience APIs)
    # ------------------------------------------------------------------

    async def read_file(self, path: Path) -> str:
        """Read a file from the project sandbox."""
        if self._sandbox is not None:
            safe_path = self._sandbox.resolve(path)
        else:
            safe_path = Path(path)
        result = await self._rpc_call("read_file", {"path": str(safe_path)})
        return str(result.get("content", "")) if isinstance(result, dict) else str(result)

    async def write_file(self, path: Path, content: str) -> None:
        """Write a file to the project sandbox."""
        if self._sandbox is not None:
            safe_path = self._sandbox.resolve(path)
        else:
            safe_path = Path(path)
        await self._rpc_call("write_file", {"path": str(safe_path), "content": content})

    async def run_tests(self, scope: str | None = None) -> dict[str, Any]:
        """Run the project test suite."""
        result = await self._rpc_call("run_tests", {"scope": scope})
        return result if isinstance(result, dict) else {"result": result}

    async def git(self, operation: str, args: list[str] | None = None) -> dict[str, Any]:
        """Perform a git operation."""
        result = await self._rpc_call("git", {"operation": operation, "args": args or []})
        return result if isinstance(result, dict) else {"result": result}

    async def shell(self, command: str) -> dict[str, Any]:
        """Execute a shell command in the project sandbox."""
        result = await self._rpc_call("shell", {"command": command})
        return result if isinstance(result, dict) else {"result": result}

    async def review(self, diff: str) -> dict[str, Any]:
        """Review a code diff."""
        result = await self._rpc_call("review", {"diff": diff})
        return result if isinstance(result, dict) else {"result": result}

    # ------------------------------------------------------------------
    # Health (override to support mock mode)
    # ------------------------------------------------------------------

    async def report_health(self) -> HealthReport:
        """Report health (mock mode = always healthy)."""
        if not self._initialized:
            return HealthReport.unhealthy("not initialized")
        if self._mock_mode:
            return HealthReport.healthy()
        return await super().report_health()
