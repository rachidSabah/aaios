"""Built-in agent implementations.

This package contains agents that ship with AAiOS itself. Third-party
agents live in plugins/ (Phase 11) and are loaded at runtime.

Phase 4 deliverables:
  - mock_agent.py — for testing the registry without real LLM calls

Future phases:
  - Phase 9: claude_code/ — ClaudeCodeCodingAgent
  - Phase 10: hermes/ — HermesDesktopAgent
  - Phase 11+: planner_agent, reflection_agent, qa_agent, etc.
"""

from __future__ import annotations

from agents._impls.mock_agent import MockAgent

__all__ = ["MockAgent"]
