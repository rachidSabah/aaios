"""Agent type Protocols — 16 type-specific extensions of GenericAgent.

Each Protocol extends ``GenericAgent`` with type-specific methods and a
capability vocabulary. Multiple implementations may exist per type; the
Supervisor's Capability Selector picks based on track record, health, cost,
and latency.

Type-specific methods are convenience APIs for direct invocation. The
Supervisor primarily uses ``execute_task`` and ``stream_progress`` (from
``GenericAgent``), but agents of a known type may be called via their
type-specific methods for tighter integration.

Reserved capability namespaces per type (see 04-component-map.md):
  - SupervisorAgent: supervise.*
  - PlannerAgent: plan.*
  - CodingAgent: code.*, test.run, git.*, shell.execute
  - DesktopAgent: desktop.*, browser.*
  - ResearchAgent: web.*, cite.*
  - BrowserAgent: browser.*
  - MemoryAgent: memory.*
  - ReflectionAgent: reflect.*
  - QAAgent: qa.*
  - SecurityAgent: security.*
  - DeploymentAgent: deploy.*
  - VisionAgent: vision.*
  - VoiceAgent: voice.*
  - DocumentAgent: doc.*
  - WorkflowAgent: workflow.*
  - CustomAgent: custom.*
"""

from __future__ import annotations

from agents._types.brow import BrowserAgent
from agents._types.cod import CodingAgent
from agents._types.cus import CustomAgent
from agents._types.dep import DeploymentAgent
from agents._types.des import DesktopAgent
from agents._types.doc import DocumentAgent
from agents._types.gen import GenericAgent
from agents._types.mem import MemoryAgent
from agents._types.pla import PlannerAgent
from agents._types.qaa import QAAgent
from agents._types.ref import ReflectionAgent
from agents._types.res import ResearchAgent
from agents._types.sec import SecurityAgent
from agents._types.sup import SupervisorAgent
from agents._types.vis import VisionAgent
from agents._types.voi import VoiceAgent
from agents._types.wfe import WorkflowAgent

__all__ = [
    "BrowserAgent",
    "CodingAgent",
    "CustomAgent",
    "DeploymentAgent",
    "DesktopAgent",
    "DocumentAgent",
    "GenericAgent",
    "MemoryAgent",
    "PlannerAgent",
    "QAAgent",
    "ReflectionAgent",
    "ResearchAgent",
    "SecurityAgent",
    "SupervisorAgent",
    "VisionAgent",
    "VoiceAgent",
    "WorkflowAgent",
]
