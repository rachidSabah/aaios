"""Hermes DesktopAgent — a DesktopAgent implementation via subprocess bridge.

This agent wraps the in-house Hermes daemon (Python + Playwright + PyAutoGUI +
Pywinauto) via a subprocess + JSON-RPC bridge. It satisfies:
  - The GenericAgent Protocol (11 methods)
  - The DesktopAgent Protocol (open_app, close_app, click, type_text,
    screenshot, ocr, find_element, manage_file)

The agent spawns the Hermes daemon as a subprocess, communicates via
newline-delimited JSON-RPC over stdin/stdout, and enforces per-task
desktop control approval (via the Permission Manager).

If the Hermes daemon binary is not available, the agent falls back to
mock mode — returns canned responses for testing.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from agents._base.subprocess_bridge import SubprocessBridgeAgent
from agents._impls.claude_code.protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    RPCErrorCode,
)
from agents._impls.hermes.capabilities import build_manifest
from core.contracts.agent import (
    AgentIdentity,
    AgentType,
    CapabilityManifest,
)
from core.contracts.health import HealthReport
from core.contracts.task import TaskRequest, TaskResult, TaskResultStatus
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = ["HermesDesktopAgent"]


class HermesDesktopAgent(SubprocessBridgeAgent):
    """A DesktopAgent implementation that wraps the Hermes daemon via subprocess.

    The agent is identified as 'hermes-desktop-v1' but the core architecture
    never references this name (INV-09). The Supervisor discovers it via
    the Agent Registry's capability index.

    DesktopAgents require explicit per-task user approval for full desktop
    control. The Permission Manager enforces this via approval gates.
    """

    def __init__(
        self,
        *,
        daemon_binary: str | None = None,
        mock_mode: bool = False,
    ) -> None:
        identity = AgentIdentity(
            agent_id="hermes-desktop-v1",
            agent_type=AgentType.DESKTOP,
            implementation_name="Hermes Desktop",
            version="1.0.0",
            vendor="AAiOS",
        )
        super().__init__(identity)
        self._daemon_binary = daemon_binary or self._find_daemon_binary()
        self._mock_mode = mock_mode or (self._daemon_binary is None)
        self._manifest: CapabilityManifest = build_manifest()

    @staticmethod
    def _find_daemon_binary() -> str | None:
        """Try to find the Hermes daemon binary on PATH."""
        for name in ("hermes", "hermes-daemon"):
            path = os.environ.get("PATH", "")
            for directory in path.split(os.pathsep):
                full = Path(directory) / name
                if full.is_file():
                    return str(full)
        return None

    async def _on_initialize(self) -> None:
        """Initialize: spawn the daemon subprocess (or enter mock mode)."""
        if self._mock_mode:
            _log.info("hermes.mock_mode", agent_id=self._identity.agent_id)
            self._health = HealthReport.healthy()
            return

        assert self._daemon_binary is not None
        try:
            self._process = await asyncio.create_subprocess_exec(
                self._daemon_binary,
                "--json-rpc",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _log.info(
                "hermes.subprocess_started",
                agent_id=self._identity.agent_id,
                pid=self._process.pid,
            )
            self._health = HealthReport.healthy()
        except Exception as e:
            _log.error("hermes.subprocess_failed", error=str(e))
            self._health = HealthReport.unhealthy(str(e))
            raise

    async def _build_manifest(self) -> CapabilityManifest:
        """Return the capability manifest."""
        return self._manifest

    async def _rpc_call(self, method: str, params: dict[str, Any]) -> Any:
        """Send a JSON-RPC call and return the result."""
        if self._mock_mode:
            return self._mock_rpc_call(method, params)

        if self._process is None or self._process.returncode is not None:
            raise RuntimeError("Daemon subprocess not running")

        request = JSONRPCRequest(method=method, params=params)
        line = request.to_line()
        assert self._process.stdin is not None
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        assert self._process.stdout is not None
        response_line = await asyncio.wait_for(
            self._process.stdout.readline(),
            timeout=120.0,
        )
        if not response_line:
            raise RuntimeError("Daemon closed unexpectedly")
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
        """Return canned responses for testing without a real daemon."""
        if method == "execute_task":
            goal = params.get("request", {}).get("goal", "")
            return TaskResult(
                task_id=params.get("request", {}).get("id", ""),
                status=TaskResultStatus.SUCCESS,
                output={"goal": goal, "result": "mock desktop execution completed"},
                duration_s=0.01,
            ).model_dump()
        if method == "screenshot":
            import base64

            # Return a minimal valid PNG (1x1 pixel) as base64
            png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\xfe\x02\xfe\xa1Yz\xc6\x00\x00\x00\x00IEND\xaeB`\x82"
            return {
                "image_base64": base64.b64encode(png_bytes).decode(),
                "width": 1920,
                "height": 1080,
            }
        if method == "ocr":
            return {"text": "Mock OCR extracted text", "confidence": 0.95}
        if method == "find_element":
            return {"found": True, "x": 100, "y": 200, "width": 50, "height": 30}
        if method == "open_app":
            return {"pid": 12345, "window_title": "Mock App"}
        if method == "close_app":
            return {"closed": True}
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
    # DesktopAgent Protocol methods
    # ------------------------------------------------------------------

    async def open_app(self, name: str) -> dict[str, Any]:
        """Open an application by name."""
        result = await self._rpc_call("open_app", {"name": name})
        return result if isinstance(result, dict) else {"result": result}

    async def close_app(self, pid: int) -> None:
        """Close an application by PID."""
        await self._rpc_call("close_app", {"pid": pid})

    async def click(self, x: int, y: int) -> None:
        """Click at screen coordinates."""
        await self._rpc_call("click", {"x": x, "y": y})

    async def type_text(self, text: str) -> None:
        """Type text via the keyboard."""
        await self._rpc_call("type_text", {"text": text})

    async def screenshot(self) -> bytes:
        """Capture the screen. Returns PNG bytes."""
        import base64

        result = await self._rpc_call("screenshot", {})
        if isinstance(result, dict) and "image_base64" in result:
            return base64.b64decode(result["image_base64"])
        return b""

    async def ocr(self, region: tuple[int, int, int, int] | None = None) -> str:
        """OCR the screen (optionally a region). Returns extracted text."""
        params: dict[str, Any] = {}
        if region is not None:
            params["region"] = list(region)
        result = await self._rpc_call("ocr", params)
        if isinstance(result, dict):
            return str(result.get("text", ""))
        return str(result)

    async def find_element(self, selector: str) -> dict[str, Any]:
        """Find a UI element by selector (text, role, or coordinates)."""
        result = await self._rpc_call("find_element", {"selector": selector})
        return result if isinstance(result, dict) else {"result": result}

    async def manage_file(self, op: str, path: Path, *args: Any) -> dict[str, Any]:
        """Perform a file management operation (open, copy, move, delete)."""
        result = await self._rpc_call(
            "manage_file",
            {
                "op": op,
                "path": str(path),
                "args": [str(a) for a in args],
            },
        )
        return result if isinstance(result, dict) else {"result": result}

    # ------------------------------------------------------------------
    # Browser operations (DesktopAgent also handles browser.* capabilities)
    # ------------------------------------------------------------------

    async def browser_navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL in a browser."""
        result = await self._rpc_call("browser_navigate", {"url": url})
        return result if isinstance(result, dict) else {"result": result}

    async def browser_click(self, selector: str) -> None:
        """Click an element matching a CSS/XPath selector."""
        await self._rpc_call("browser_click", {"selector": selector})

    async def browser_input(self, selector: str, value: str) -> None:
        """Type into an input element in the browser."""
        await self._rpc_call("browser_input", {"selector": selector, "value": value})

    async def browser_extract(self, selector: str) -> dict[str, Any]:
        """Extract data from elements matching a selector."""
        result = await self._rpc_call("browser_extract", {"selector": selector})
        return result if isinstance(result, dict) else {"result": result}

    async def browser_screenshot(self) -> bytes:
        """Capture the browser page. Returns PNG bytes."""
        import base64

        result = await self._rpc_call("browser_screenshot", {})
        if isinstance(result, dict) and "image_base64" in result:
            return base64.b64decode(result["image_base64"])
        return b""

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
