"""Analytics — high-level aggregations for the dashboard analytics page.

Wraps the MetricsCollector with convenience queries that produce ready-to-
render summaries (top agents by usage, cost breakdown by capability,
latency percentiles, etc.).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from services.dashboard.metrics_collector import MetricsCollector

__all__ = ["Analytics"]


class Analytics:
    """High-level analytics queries over collected metrics.

    All methods are async (the underlying collector uses a lock).
    Returns plain dicts/lists so the API can serialize them directly.
    """

    def __init__(self, collector: MetricsCollector) -> None:
        self._collector = collector

    async def summary(self) -> dict[str, Any]:
        """Top-line summary: totals, rates, top agents/capabilities."""
        snap = await self._collector.snapshot()
        minute_buckets = snap.buckets_last_hour[-60:]
        total_events = sum(b["sample_count"] for b in minute_buckets)
        total_cost = sum(b["total_cost_usd"] for b in minute_buckets)
        success_count = sum(b["success_count"] for b in minute_buckets)
        failure_count = sum(b["failure_count"] for b in minute_buckets)
        success_rate = (
            success_count / (success_count + failure_count)
            if (success_count + failure_count) > 0
            else 0.0
        )
        avg_latency = (
            sum(b["avg_duration_s"] * b["sample_count"] for b in minute_buckets) / total_events
            if total_events > 0
            else 0.0
        )
        agent_counter: Counter[str] = Counter()
        cap_counter: Counter[str] = Counter()
        for b in minute_buckets:
            agent_counter.update(b["agent_counts"])
            cap_counter.update(b["capability_counts"])
        return {
            "window_minutes": 60,
            "total_events": total_events,
            "events_per_minute": total_events / 60.0 if total_events else 0.0,
            "success_rate": success_rate,
            "avg_latency_s": avg_latency,
            "total_cost_usd": total_cost,
            "top_agents": agent_counter.most_common(10),
            "top_capabilities": cap_counter.most_common(10),
            "active_agents": snap.active_agents,
            "active_capabilities": snap.active_capabilities,
        }

    async def cost_breakdown(self, window_minutes: int = 60) -> dict[str, Any]:
        """Cost breakdown by capability over the window."""
        snap = await self._collector.snapshot()
        buckets = snap.buckets_last_hour[-window_minutes:]
        cost_by_cap: Counter[str] = Counter()
        # The collector doesn't keep per-capability cost directly; we approximate
        # by distributing the bucket cost across the capabilities in that bucket
        # weighted by their sample counts.
        for b in buckets:
            cap_counts = b["capability_counts"]
            total_in_bucket = sum(cap_counts.values()) or 1
            for cap, count in cap_counts.items():
                cost_by_cap[cap] += b["total_cost_usd"] * (count / total_in_bucket)
        return {
            "window_minutes": window_minutes,
            "by_capability": [
                {"capability": cap, "cost_usd": round(cost, 6)}
                for cap, cost in cost_by_cap.most_common()
            ],
            "total_cost_usd": round(sum(cost_by_cap.values()), 6),
        }

    async def latency_percentiles(
        self,
        window_minutes: int = 60,
    ) -> dict[str, Any]:
        """Latency percentiles (p50, p90, p95, p99) over the window.

        Computed from per-bucket average latencies weighted by sample count.
        """
        snap = await self._collector.snapshot()
        buckets = snap.buckets_last_hour[-window_minutes:]
        latencies: list[float] = []
        for b in buckets:
            for _ in range(b["sample_count"]):
                latencies.append(b["avg_duration_s"])
        if not latencies:
            return {
                "window_minutes": window_minutes,
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "count": 0,
            }
        latencies.sort()
        n = len(latencies)

        def pct(p: float) -> float:
            idx = max(0, min(n - 1, math.ceil(p * n) - 1))
            return latencies[idx]

        return {
            "window_minutes": window_minutes,
            "p50": round(pct(0.50), 4),
            "p90": round(pct(0.90), 4),
            "p95": round(pct(0.95), 4),
            "p99": round(pct(0.99), 4),
            "count": n,
        }

    async def throughput_series(self, window_minutes: int = 60) -> list[dict[str, Any]]:
        """Events-per-minute throughput time series."""
        return await self._collector.timeseries(
            metric="event_count",
            window_minutes=window_minutes,
        )

    async def success_rate_series(
        self,
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Success-rate time series (0.0-1.0 per minute bucket)."""
        return await self._collector.timeseries(
            metric="success_rate",
            window_minutes=window_minutes,
        )
