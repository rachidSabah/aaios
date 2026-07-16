"""Benchmark models — Pydantic definitions for performance metrics and latency reports."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class BenchmarkResult(BaseModel):
    """Execution latency and system throughput metrics collected during benchmark run."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cold_boot_ms: float = 0.0
    warm_boot_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    startup_latency_ms: float = 0.0
    agent_startup_ms: float = 0.0
    provider_latency_ms: float = 0.0
    memory_latency_ms: float = 0.0
    database_latency_ms: float = 0.0
    workflow_throughput: float = 0.0
    task_throughput: float = 0.0
    optimization_suggestions: list[str] = Field(default_factory=list)
