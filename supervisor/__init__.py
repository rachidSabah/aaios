"""Supervisor package — the orchestrator-in-chief + planning agents.

The Supervisor owns the task lifecycle. It calls the Planner to decompose
goals, dispatches steps via the Capability Selector, invokes Reflection
and Self-Correction, and validates with QA.

Components:
  - ``capability_selector.py`` — scores and picks agents from the registry
  - ``planner.py`` — LlmPlanner (decomposes goals into DAG plans)
  - ``reflection.py`` — DefaultReflectionAgent (critiques outputs)
  - ``correction.py`` — DefaultSelfCorrectionAgent (repairs rejected outputs)
  - ``qa.py`` — DefaultQAAgent (validates deliverables)
  - ``agent.py`` — DefaultSupervisor (the main supervisor loop)
"""

from __future__ import annotations

from supervisor.agent import DefaultSupervisor
from supervisor.capability_selector import (
    CapabilitySelector,
    NoCandidateError,
    SelectionResult,
)
from supervisor.correction import DefaultSelfCorrectionAgent
from supervisor.planner import LlmPlanner, PlanResult
from supervisor.qa import DefaultQAAgent, QAVerdict
from supervisor.reflection import DefaultReflectionAgent, ReflectionVerdict

__all__ = [
    "CapabilitySelector",
    "DefaultQAAgent",
    "DefaultReflectionAgent",
    "DefaultSelfCorrectionAgent",
    "DefaultSupervisor",
    "LlmPlanner",
    "NoCandidateError",
    "PlanResult",
    "QAVerdict",
    "ReflectionVerdict",
    "SelectionResult",
]
