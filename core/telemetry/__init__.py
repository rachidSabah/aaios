"""Telemetry — OpenTelemetry SDK wiring (traces, metrics, logs export).

Opt-out, never opt-in. Every component should obtain its tracer and meter
from here, not directly from OpenTelemetry. This way we can swap exporters
without touching every file.

Two exporters:
  - InProcessExporter: default; metrics visible on the dashboard
  - OTLPExporter: optional; exports to an external backend (Jaeger, Tempo,
    Honeycomb, Datadog, Application Insights)
"""

from __future__ import annotations

from core.telemetry.setup import (
    TelemetryConfig,
    get_meter,
    get_tracer,
    init_telemetry,
    shutdown_telemetry,
)

__all__ = [
    "TelemetryConfig",
    "get_meter",
    "get_tracer",
    "init_telemetry",
    "shutdown_telemetry",
]
