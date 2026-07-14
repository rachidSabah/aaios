"""Agents package — GenericAgent types, base classes, and built-in implementations.

Layering (INV-01): L3 (agents) may import from L1 (core) and L2 (services).
L3 may NOT import from L4 (supervisor, orchestrator) or L5 (surfaces).

Structure:
  - ``_types/`` — the 16 type Protocols extending GenericAgent
  - ``_base/`` — implementation-style base classes (InProcess, SubprocessBridge, RemoteService)
  - ``_impls/`` — built-in agent implementations (Phase 4: mock_agent only)
"""

from __future__ import annotations

from agents._base import InProcessAgent, RemoteServiceAgent, SubprocessBridgeAgent
from agents._impls import MockAgent
from agents._types import (
    BrowserAgent,
    CodingAgent,
    CustomAgent,
    DeploymentAgent,
    DesktopAgent,
    DocumentAgent,
    GenericAgent,
    MemoryAgent,
    PlannerAgent,
    QAAgent,
    ReflectionAgent,
    ResearchAgent,
    SecurityAgent,
    SupervisorAgent,
    VisionAgent,
    VoiceAgent,
    WorkflowAgent,
)

__all__ = [
    "BrowserAgent",
    "CodingAgent",
    "CustomAgent",
    "DeploymentAgent",
    "DesktopAgent",
    "DocumentAgent",
    "GenericAgent",
    "InProcessAgent",
    "MemoryAgent",
    "MockAgent",
    "PlannerAgent",
    "QAAgent",
    "ReflectionAgent",
    "RemoteServiceAgent",
    "ResearchAgent",
    "SecurityAgent",
    "SubprocessBridgeAgent",
    "SupervisorAgent",
    "VisionAgent",
    "VoiceAgent",
    "WorkflowAgent",
]
