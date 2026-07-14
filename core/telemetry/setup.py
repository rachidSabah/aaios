"""OpenTelemetry setup — tracer, meter, exporter wiring.

Usage:
    from core.telemetry import init_telemetry, get_tracer, get_meter

    init_telemetry()  # at boot
    tracer = get_tracer(__name__)
    meter = get_meter(__name__)

    with tracer.start_as_current_span('agent.dispatch') as span:
        span.set_attribute('agent_id', agent_id)
        ...

    counter = meter.create_counter('tasks_completed')
    counter.add(1, {'priority': 'normal'})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)


@dataclass
class TelemetryConfig:
    """Configuration for the telemetry system."""

    service_name: str = "aaios"
    service_version: str = "0.1.0.dev0"
    service_namespace: str = "aaios"
    service_instance_id: str = "local"
    otlp_endpoint: str | None = None  # e.g. 'http://localhost:4317'
    console_export: bool = False  # for dev/debug
    trace_sample_rate: float = 1.0  # 1.0 = sample everything
    metric_export_interval_s: int = 5
    extra_resource_attrs: dict[str, str] = field(default_factory=dict)


_INITIALIZED: bool = False
_TRACER_PROVIDER: TracerProvider | None = None
_METER_PROVIDER: MeterProvider | None = None


def init_telemetry(config: TelemetryConfig | None = None) -> None:
    """Initialize OpenTelemetry — tracer + meter providers.

    Idempotent. Subsequent calls update exporters if config changes.

    Args:
        config: telemetry configuration. If None, uses defaults (no OTLP,
            no console export — in-process only).
    """
    global _INITIALIZED, _TRACER_PROVIDER, _METER_PROVIDER
    if _INITIALIZED and config is None:
        return
    config = config or TelemetryConfig()

    resource = Resource.create(
        {
            "service.name": config.service_name,
            "service.version": config.service_version,
            "service.namespace": config.service_namespace,
            "service.instance.id": config.service_instance_id,
            **config.extra_resource_attrs,
        },
    )

    # --- Tracer provider ---
    tracer_provider = TracerProvider(resource=resource)

    # Always add a console exporter in dev mode (no OTLP)
    if config.console_export or config.otlp_endpoint is None:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter()),
        )

    if config.otlp_endpoint:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otlp_endpoint, insecure=True)),
        )

    trace.set_tracer_provider(tracer_provider)
    _TRACER_PROVIDER = tracer_provider

    # --- Meter provider ---
    metric_readers: list[Any] = []
    if config.console_export or config.otlp_endpoint is None:
        metric_readers.append(
            PeriodicExportingMetricReader(
                ConsoleMetricExporter(),
                export_interval_millis=config.metric_export_interval_s * 1000,
            ),
        )
    if config.otlp_endpoint:
        metric_readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=config.otlp_endpoint, insecure=True),
                export_interval_millis=config.metric_export_interval_s * 1000,
            ),
        )

    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    _METER_PROVIDER = meter_provider

    _INITIALIZED = True


def shutdown_telemetry() -> None:
    """Flush and shutdown all telemetry providers. Call on system shutdown."""
    global _INITIALIZED, _TRACER_PROVIDER, _METER_PROVIDER
    if _TRACER_PROVIDER is not None:
        _TRACER_PROVIDER.shutdown()
    if _METER_PROVIDER is not None:
        _METER_PROVIDER.shutdown()
    _TRACER_PROVIDER = None
    _METER_PROVIDER = None
    _INITIALIZED = False


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for ``name`` (usually the module name).

    If telemetry hasn't been initialized, returns a no-op tracer (safe
    default for tests).
    """
    if not _INITIALIZED:
        init_telemetry()
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """Return a meter for ``name`` (usually the module name)."""
    if not _INITIALIZED:
        init_telemetry()
    return metrics.get_meter(name)
