"""Metrics Collector — subscribes to the event bus and records time-series
metrics for the live monitoring dashboard.

The collector keeps an in-memory ring buffer of recent events (default 10k)
and aggregates them into time-bucketed counters per event type and per
agent. This powers the live monitoring page and the analytics charts.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from core.contracts.event import Event
from core.event_bus import EventBus
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "MetricBucket",
    "MetricSample",
    "MetricsCollector",
    "MonitorSnapshot",
]


@dataclass
class MetricSample:
    """A single timestamped metric event."""

    timestamp: float
    event_type: str
    agent_id: str | None = None
    capability: str | None = None
    duration_s: float | None = None
    success: bool | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricBucket:
    """Aggregated metrics for a time bucket (e.g. 1 minute)."""

    bucket_start: float
    event_counts: dict[str, int] = field(default_factory=dict)
    agent_counts: dict[str, int] = field(default_factory=dict)
    capability_counts: dict[str, int] = field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    total_duration_s: float = 0.0
    total_cost_usd: float = 0.0
    sample_count: int = 0

    def add(self, sample: MetricSample) -> None:
        self.event_counts[sample.event_type] = (
            self.event_counts.get(sample.event_type, 0) + 1
        )
        if sample.agent_id:
            self.agent_counts[sample.agent_id] = (
                self.agent_counts.get(sample.agent_id, 0) + 1
            )
        if sample.capability:
            self.capability_counts[sample.capability] = (
                self.capability_counts.get(sample.capability, 0) + 1
            )
        if sample.success is True:
            self.success_count += 1
        elif sample.success is False:
            self.failure_count += 1
        if sample.duration_s is not None:
            self.total_duration_s += sample.duration_s
        if sample.cost_usd is not None:
            self.total_cost_usd += sample.cost_usd
        self.sample_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket_start": self.bucket_start,
            "sample_count": self.sample_count,
            "event_counts": dict(self.event_counts),
            "agent_counts": dict(self.agent_counts),
            "capability_counts": dict(self.capability_counts),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": (
                self.success_count / self.sample_count
                if self.sample_count > 0
                else 0.0
            ),
            "avg_duration_s": (
                self.total_duration_s / self.sample_count
                if self.sample_count > 0
                else 0.0
            ),
            "total_cost_usd": self.total_cost_usd,
        }


@dataclass
class MonitorSnapshot:
    """Point-in-time snapshot of system state for the live monitor."""

    timestamp: float
    total_events: int
    events_last_minute: int
    events_last_hour: int
    active_agents: list[str]
    active_capabilities: list[str]
    recent_events: list[dict[str, Any]]
    buckets_last_hour: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_events": self.total_events,
            "events_last_minute": self.events_last_minute,
            "events_last_hour": self.events_last_hour,
            "active_agents": self.active_agents,
            "active_capabilities": self.active_capabilities,
            "recent_events": self.recent_events,
            "buckets_last_hour": self.buckets_last_hour,
        }


class MetricsCollector:
    """Collects metrics from the event bus.

    Subscribe once with `await collector.subscribe(bus)`. After that, every
    event published on the bus is recorded. The collector keeps:
      - A ring buffer of recent samples (default 10,000)
      - Per-minute buckets for the last hour (60 buckets)
      - Per-hour buckets for the last 24 hours (24 buckets)
    """

    def __init__(
        self,
        recent_buffer_size: int = 10_000,
        minute_bucket_count: int = 60,
        hour_bucket_count: int = 24,
    ) -> None:
        self._recent: deque[MetricSample] = deque(maxlen=recent_buffer_size)
        self._minute_buckets: deque[MetricBucket] = deque(maxlen=minute_bucket_count)
        self._hour_buckets: deque[MetricBucket] = deque(maxlen=hour_bucket_count)
        self._bucket_span_s: float = 60.0  # 1-minute buckets
        self._hour_span_s: float = 3600.0  # 1-hour buckets
        self._lock = asyncio.Lock()
        self._subscribed = False

    async def subscribe(self, bus: EventBus) -> None:
        """Subscribe to all events on the bus."""
        if self._subscribed:
            return
        bus.subscribe("*", self.handle)
        self._subscribed = True
        _log.info("MetricsCollector subscribed to event bus")

    async def handle(self, event: Event) -> None:
        """EventHandler protocol — record the event."""
        await self.record_event(event)

    async def record_event(self, event: Event) -> None:
        """Record an event as a metric sample."""
        # event.timestamp is a datetime; convert to epoch float
        ts = event.timestamp.timestamp()
        sample = MetricSample(
            timestamp=ts,
            event_type=event.topic,
            agent_id=str(event.payload.get("agent_id"))
            if "agent_id" in event.payload
            else None,
            capability=str(event.payload.get("capability"))
            if "capability" in event.payload
            else None,
            duration_s=float(event.payload["duration_s"])
            if "duration_s" in event.payload
            else None,
            success=bool(event.payload["success"])
            if "success" in event.payload
            else None,
            cost_usd=float(event.payload["cost_usd"])
            if "cost_usd" in event.payload
            else None,
        )
        async with self._lock:
            self._recent.append(sample)
            self._place_in_bucket(sample, self._minute_buckets, self._bucket_span_s)
            self._place_in_bucket(sample, self._hour_buckets, self._hour_span_s)

    def _place_in_bucket(
        self,
        sample: MetricSample,
        buckets: deque[MetricBucket],
        span_s: float,
    ) -> None:
        bucket_start = (int(sample.timestamp) // int(span_s)) * span_s
        if buckets and buckets[-1].bucket_start == bucket_start:
            buckets[-1].add(sample)
        else:
            # Fill in empty buckets if there's a gap
            if buckets:
                last = buckets[-1].bucket_start
                gap = (bucket_start - last) / span_s
                maxlen = buckets.maxlen or 0
                for _ in range(int(gap) - 1):
                    if len(buckets) >= maxlen:
                        break
                    buckets.append(MetricBucket(bucket_start=last + span_s))
            new_bucket = MetricBucket(bucket_start=bucket_start)
            new_bucket.add(sample)
            buckets.append(new_bucket)

    async def snapshot(self) -> MonitorSnapshot:
        """Get a point-in-time snapshot of system state."""
        now = time.time()
        async with self._lock:
            minute_ago = now - 60.0
            hour_ago = now - 3600.0
            events_last_minute = sum(
                1 for s in self._recent if s.timestamp >= minute_ago
            )
            events_last_hour = sum(
                1 for s in self._recent if s.timestamp >= hour_ago
            )
            active_agents = sorted(
                {s.agent_id for s in self._recent if s.agent_id and s.timestamp >= hour_ago}
            )
            active_capabilities = sorted(
                {s.capability for s in self._recent if s.capability and s.timestamp >= hour_ago}
            )
            recent_events = [
                {
                    "timestamp": s.timestamp,
                    "event_type": s.event_type,
                    "agent_id": s.agent_id,
                    "capability": s.capability,
                    "success": s.success,
                    "duration_s": s.duration_s,
                }
                for s in list(self._recent)[-20:]
            ]
            buckets_last_hour = [b.to_dict() for b in self._minute_buckets]
            return MonitorSnapshot(
                timestamp=now,
                total_events=len(self._recent),
                events_last_minute=events_last_minute,
                events_last_hour=events_last_hour,
                active_agents=active_agents,
                active_capabilities=active_capabilities,
                recent_events=list(reversed(recent_events)),
                buckets_last_hour=buckets_last_hour,
            )

    async def timeseries(
        self,
        metric: str = "event_count",
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Return a time series for the given metric over the window."""
        async with self._lock:
            buckets = list(self._minute_buckets)[-window_minutes:]
            series: list[dict[str, Any]] = []
            for b in buckets:
                d = b.to_dict()
                if metric == "event_count":
                    value = b.sample_count
                elif metric == "success_rate":
                    value = d["success_rate"]
                elif metric == "avg_duration_s":
                    value = d["avg_duration_s"]
                elif metric == "cost_usd":
                    value = d["total_cost_usd"]
                else:
                    value = b.event_counts.get(metric, 0)
                series.append(
                    {
                        "timestamp": b.bucket_start,
                        "value": value,
                    }
                )
            return series
