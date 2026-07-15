"""Capability manifest for the Voice & Vision Agent.

Advertises: audio.transcribe (ASR), audio.synthesize (TTS),
image.analyze (vision-language understanding), image.generate (text-to-image),
multimodal.chat (combined text + image + audio chat).

This agent is one implementation of the multimodal agent type. Future
implementations (WhisperLocal, DALL-E Local, etc.) would advertise the
same capabilities.
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
    "audio.transcribe",  # ASR — speech to text
    "audio.synthesize",  # TTS — text to speech
    "image.analyze",     # VLM — image understanding
    "image.generate",    # text-to-image
    "multimodal.chat",   # combined text + image + audio chat
]


CAPABILITIES: list[Capability] = [
    Capability(
        namespace="audio.transcribe",
        description="Transcribe speech from audio bytes to text",
        side_effects=[SideEffect(kind="model.inference", scope="external")],
        requires_permission=Permission(name="gateway.net.request"),
    ),
    Capability(
        namespace="audio.synthesize",
        description="Synthesize speech from text. Returns audio bytes.",
        side_effects=[SideEffect(kind="model.inference", scope="external")],
        requires_permission=Permission(name="gateway.net.request"),
    ),
    Capability(
        namespace="image.analyze",
        description="Analyze an image with a text prompt. Returns description.",
        side_effects=[SideEffect(kind="model.inference", scope="external")],
        requires_permission=Permission(name="gateway.net.request"),
    ),
    Capability(
        namespace="image.generate",
        description="Generate an image from a text prompt. Returns PNG bytes.",
        side_effects=[SideEffect(kind="model.inference", scope="external")],
        requires_permission=Permission(name="gateway.net.request"),
    ),
    Capability(
        namespace="multimodal.chat",
        description="Multimodal chat — accepts text + optional image/audio",
        side_effects=[SideEffect(kind="model.inference", scope="external")],
        requires_permission=Permission(name="gateway.net.request"),
    ),
]


def build_manifest() -> CapabilityManifest:
    """Build the capability manifest for the Voice & Vision Agent."""
    identity = AgentIdentity(
        agent_id="voice-vision-v1",
        agent_type=AgentType.VISION,
        implementation_name="Voice & Vision Agent",
        version="2.0.0",
        vendor="AAiOS",
    )
    return CapabilityManifest(
        identity=identity,
        capabilities=CAPABILITIES,
        resource_requirements=ResourceRequirements(
            cpu_cores=2.0,
            memory_mb=2048,  # multimodal models need more memory
            disk_mb=500,
            network=True,
        ),
        permissions_required=[
            Permission(name="gateway.net.request"),
            Permission(name="gateway.fs.write"),  # for saving generated audio/images
        ],
        health_check=HealthCheckSpec(
            interval_s=30,
            timeout_s=10,
            unhealthy_threshold=3,
            degraded_threshold=1,
        ),
        timeout_defaults=TimeoutDefaults(
            initialize_s=30.0,
            discover_capabilities_s=5.0,
            execute_task_s=120.0,  # image generation can be slow
            cancel_task_s=5.0,
            report_health_s=10.0,
        ),
        cost_model=CostModel(
            fixed_usd=0.0,
            per_token_usd=0.0,  # cost tracked via model router
            per_second_usd=0.0,
        ),
    )
