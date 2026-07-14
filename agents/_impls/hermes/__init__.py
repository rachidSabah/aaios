"""Hermes DesktopAgent — one implementation of the DesktopAgent type.

A subprocess bridge that wraps the Hermes desktop daemon via JSON-RPC.
Satisfies both the GenericAgent Protocol (11 methods) and the DesktopAgent
Protocol (open_app, close_app, click, type_text, screenshot, ocr,
find_element, manage_file).

If no real daemon binary is available, the agent runs in "mock mode" —
returns canned responses for testing.
"""

from __future__ import annotations

from agents._impls.hermes.agent import HermesDesktopAgent
from agents._impls.hermes.capabilities import build_manifest

__all__ = ["HermesDesktopAgent", "build_manifest"]
