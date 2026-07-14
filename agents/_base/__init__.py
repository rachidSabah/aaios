"""Implementation-style base classes for agents.

Three styles, all satisfying ``GenericAgent``:
  - ``InProcessAgent``: pure-Python class in the same process. Computationally
    cheap, no isolation needed. Used by Reflection, QA (deterministic parts),
    Memory, Workflow.
  - ``SubprocessBridgeAgent``: wraps an external CLI/daemon via JSON-RPC over
    stdin/stdout. Used by CodingAgent (Claude Code) and DesktopAgent (Hermes).
  - ``RemoteServiceAgent``: talks to a separate agent process via HTTP/gRPC.
    Used for heavy agents deployed separately (e.g. GPU-bound VisionAgent).

The Supervisor does not know which style an agent uses. The Agent Registry
does, and uses it for health-check strategy and resource accounting, but
never leaks this detail to the Supervisor.
"""

from __future__ import annotations

from agents._base.in_process import InProcessAgent
from agents._base.remote_service import RemoteServiceAgent
from agents._base.subprocess_bridge import SubprocessBridgeAgent

__all__ = [
    "InProcessAgent",
    "RemoteServiceAgent",
    "SubprocessBridgeAgent",
]
