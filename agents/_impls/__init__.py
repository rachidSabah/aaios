"""Built-in agent implementations.

This package contains agents that ship with AAiOS itself. Third-party
agents live in plugins/ (Phase 11) and are loaded at runtime.

Phase 4: mock_agent.py — for testing the registry without real LLM calls
Phase 9: claude_code/ — ClaudeCodeCodingAgent (subprocess bridge)
Phase 10: hermes/ — HermesDesktopAgent (subprocess bridge)
v2.0: voice_vision/ — VoiceVisionAgent (multimodal ASR/TTS/VLM/image-gen)
"""

from __future__ import annotations

from agents._impls.claude_code import ClaudeCodeCodingAgent
from agents._impls.hermes import HermesDesktopAgent
from agents._impls.mock_agent import MockAgent
from agents._impls.voice_vision import VoiceVisionAgent

__all__ = [
    "ClaudeCodeCodingAgent",
    "HermesDesktopAgent",
    "MockAgent",
    "VoiceVisionAgent",
]
