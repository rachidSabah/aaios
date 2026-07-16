"""Benchmark package."""

from __future__ import annotations

from services.benchmark.manager import BenchmarkManager
from services.benchmark.models import BenchmarkResult

__all__ = ["BenchmarkManager", "BenchmarkResult"]
