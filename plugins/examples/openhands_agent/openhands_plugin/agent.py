"""OpenHands agent plugin — a scaffold showing how to add a future CodingAgent.

This is a SCAFFOLD, not a working implementation. It demonstrates the
pattern for adding a new CodingAgent implementation behind the
GenericAgent interface. The Supervisor treats it identically to the
built-in coding agent — capability-based selection, not name-based.
"""

from __future__ import annotations

from agents._base.subprocess_bridge import SubprocessBridgeAgent
from core.contracts.agent import (
    AgentIdentity,
    AgentType,
    Capability,
    CapabilityManifest,
)
from core.contracts.health import HealthReport
from core.contracts.task import TaskRequest, TaskResult, TaskResultStatus


class OpenHandsAgent(SubprocessBridgeAgent):
    """An OpenHands coding agent (scaffold).

    This is a CodingAgent implementation that wraps the OpenHands CLI.
    It advertises the same capabilities as other CodingAgent implementations
    (code.read, code.write, etc.), so the Capability Selector can choose
    between it and other coding agents based on track record, cost, and
    user preference.

    The Supervisor NEVER references this agent by name (INV-09). It discovers
    it via the Agent Registry's capability index.
    """

    def __init__(self) -> None:
        identity = AgentIdentity(
            agent_id="openhands-v1",
            agent_type=AgentType.CODING,
            implementation_name="OpenHands",
            version="0.1.0",
            vendor="Third-party",
        )
        super().__init__(identity)

    async def _on_initialize(self) -> None:
        """Initialize: spawn the OpenHands subprocess.

        TODO: implement real subprocess spawning via the Gateway.
        For now, run in mock mode.
        """
        self._health = HealthReport.healthy()

    async def _build_manifest(self) -> CapabilityManifest:
        """Return the capability manifest (same capabilities as other CodingAgents)."""
        return CapabilityManifest(
            identity=self._identity,
            capabilities=[
                Capability(namespace="code.read", description="Read source code files"),
                Capability(namespace="code.write", description="Write source code files"),
                Capability(namespace="code.refactor", description="Refactor code"),
                Capability(namespace="code.review", description="Review a code diff"),
                Capability(namespace="test.run", description="Run tests"),
                Capability(namespace="shell.execute", description="Execute shell commands"),
            ],
        )

    async def _rpc_call(self, method: str, params: dict) -> object:
        """Send a JSON-RPC call to the OpenHands subprocess.

        TODO: implement real JSON-RPC communication.
        """
        return {"mock": True, "method": method}

    async def _execute(self, request: TaskRequest) -> TaskResult:
        """Execute a coding task via OpenHands.

        TODO: implement real execution via _rpc_call.
        """
        return TaskResult(
            task_id=request.id,
            status=TaskResultStatus.SUCCESS,
            output={"goal": request.goal, "result": "OpenHands scaffold — not implemented yet"},
        )
