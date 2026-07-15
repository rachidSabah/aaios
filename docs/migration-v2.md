# AAiOS v2.0 Migration Guide

This guide covers upgrading from v1.0.x to v2.0.

## Overview

v2.0 is a **superset** of v1.0 — no breaking changes. All v1.0 APIs,
agents, and configurations continue to work unchanged. v2.0 adds five
new agents and a production engineering pass.

## What's New

### 1. Supervisor Intelligence
The supervisor now learns from execution history. No action needed —
the adaptive router starts learning automatically once you run tasks.

### 2. Dashboard
Visit `/workflows`, `/monitoring`, `/analytics` in the dashboard for
visual workflow building, live monitoring, and analytics.

### 3. Windows Native
On Windows 11 / Server 2022, you can now:
- Install AAiOS as a Windows Service (`sc.exe create AAiOS binPath=...`)
- Run agents in Job Objects (resource limits + kill-on-close)
- Sandboxed agent execution via AppContainer
- WDAC code-integrity policies
- Scheduled tasks via Task Scheduler

### 4. Provider Validation
Run `aaios doctor --providers` to verify each configured provider's API
key works. Returns a structured report with status + latency per provider.

### 5. Distributed Runtime
Multi-machine orchestration. Register remote nodes via:
```python
from services.distributed import NodeRegistry
registry = NodeRegistry()
await registry.register(address="10.0.0.2:8000", capabilities=["code.generate"])
```

### 6. Voice & Vision
Multimodal agent for ASR, TTS, image understanding, and image generation.
Register via:
```python
from agents import VoiceVisionAgent
agent = VoiceVisionAgent(mock_mode=False)  # uses ModelRouter in live mode
```

## Configuration Changes

None. v2.0 uses the same `config.yaml` schema as v1.0.

## Database Migrations

None. v2.0 uses the same schema as v1.0.

## Breaking Changes

None.

## Deprecations

None in v2.0. v1.0 APIs remain fully supported.

## Rolling Back

To roll back to v1.0:
```bash
git checkout v1.0.0
```

No data migration is required — v2.0 does not modify the v1.0 data format.
