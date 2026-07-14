"""Capability manifest for the Hermes DesktopAgent.

Advertises: desktop.ui.click, desktop.ui.find_element, desktop.input.type_text,
desktop.screen.screenshot, desktop.screen.ocr, desktop.app.open, desktop.app.close,
desktop.file.manage, browser.navigate, browser.click, browser.input, browser.extract,
browser.screenshot.

Hermes is one implementation of the DesktopAgent type. Future implementations
(AutoHotkey, pywinauto, OS-native) would advertise the same capabilities.
"""

from __future__ import annotations

from core.contracts.agent import (
    AgentIdentity,
    AgentType,
    Capability,
    CapabilityManifest,
    CostModel,
    HealthCheckSpec,
    ResourceRequirements,
    SideEffect,
    TimeoutDefaults,
)
from core.contracts.permission import Permission

__all__ = ["build_manifest", "CAPABILITIES", "CAPABILITY_NAMESPACES"]


CAPABILITY_NAMESPACES = [
    "desktop.ui.click",
    "desktop.ui.find_element",
    "desktop.input.type_text",
    "desktop.input.key_press",
    "desktop.screen.screenshot",
    "desktop.screen.ocr",
    "desktop.app.open",
    "desktop.app.close",
    "desktop.file.manage",
    "browser.navigate",
    "browser.click",
    "browser.input",
    "browser.extract",
    "browser.screenshot",
]


CAPABILITIES: list[Capability] = [
    Capability(
        namespace="desktop.ui.click",
        description="Click at screen coordinates or on a UI element",
        side_effects=[SideEffect(kind="desktop.input", scope="screen")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="desktop.ui.find_element",
        description="Find a UI element by selector (text, role, or coordinates)",
        side_effects=[SideEffect(kind="desktop.screen", scope="screen")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="desktop.input.type_text",
        description="Type text via the keyboard",
        side_effects=[SideEffect(kind="desktop.input", scope="keyboard")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="desktop.input.key_press",
        description="Press a specific key or key combination",
        side_effects=[SideEffect(kind="desktop.input", scope="keyboard")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="desktop.screen.screenshot",
        description="Capture the screen. Returns PNG bytes.",
        side_effects=[SideEffect(kind="desktop.screen", scope="screen")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="desktop.screen.ocr",
        description="OCR the screen or a region. Returns extracted text.",
        side_effects=[SideEffect(kind="desktop.screen", scope="screen")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="desktop.app.open",
        description="Open an application by name",
        side_effects=[SideEffect(kind="process.spawn", scope="system")],
        requires_permission=Permission(name="gateway.process.spawn"),
    ),
    Capability(
        namespace="desktop.app.close",
        description="Close an application by PID or window title",
        side_effects=[SideEffect(kind="process.spawn", scope="system")],
        requires_permission=Permission(name="gateway.process.spawn"),
    ),
    Capability(
        namespace="desktop.file.manage",
        description="Perform file management operations (open, copy, move, delete)",
        side_effects=[SideEffect(kind="fs.write", scope="system")],
        requires_permission=Permission(name="gateway.fs.write"),
    ),
    Capability(
        namespace="browser.navigate",
        description="Navigate to a URL in a browser",
        side_effects=[SideEffect(kind="net.request", scope="web")],
        requires_permission=Permission(name="gateway.net.request"),
    ),
    Capability(
        namespace="browser.click",
        description="Click an element matching a CSS/XPath selector",
        side_effects=[SideEffect(kind="desktop.input", scope="browser")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="browser.input",
        description="Type into an input element in the browser",
        side_effects=[SideEffect(kind="desktop.input", scope="browser")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="browser.extract",
        description="Extract data from elements matching a selector",
        side_effects=[SideEffect(kind="desktop.screen", scope="browser")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
    Capability(
        namespace="browser.screenshot",
        description="Capture the browser page. Returns PNG bytes.",
        side_effects=[SideEffect(kind="desktop.screen", scope="browser")],
        requires_permission=Permission(name="gateway.desktop.input"),
    ),
]


def build_manifest() -> CapabilityManifest:
    """Build the capability manifest for the Hermes agent."""
    identity = AgentIdentity(
        agent_id="hermes-desktop-v1",
        agent_type=AgentType.DESKTOP,
        implementation_name="Hermes Desktop",
        version="1.0.0",
        vendor="AAiOS",
    )
    return CapabilityManifest(
        identity=identity,
        capabilities=CAPABILITIES,
        resource_requirements=ResourceRequirements(
            cpu_cores=2.0,
            memory_mb=1024,  # higher than coding agent (Playwright + PyAutoGUI)
            disk_mb=200,
            network=True,
        ),
        permissions_required=[
            Permission(name="gateway.desktop.input"),
            Permission(name="gateway.process.spawn"),
            Permission(name="gateway.fs.write"),
            Permission(name="gateway.net.request"),
        ],
        health_check=HealthCheckSpec(
            interval_s=15,
            timeout_s=5,
            unhealthy_threshold=3,
            degraded_threshold=1,
        ),
        timeout_defaults=TimeoutDefaults(
            initialize_s=30.0,
            discover_capabilities_s=5.0,
            execute_task_s=120.0,  # desktop tasks are usually shorter
            cancel_task_s=3.0,
            report_health_s=5.0,
        ),
        cost_model=CostModel(
            fixed_usd=0.0,  # local execution, no LLM cost (unless vision is used)
            per_token_usd=0.0,
            per_second_usd=0.0,
        ),
    )
