"""AAiOS v3.1 — Enterprise Intelligence Layer.

A continuously self-improving intelligence system that makes AAiOS
self-analyzing, self-optimizing, and self-healing. The system monitors
its own health, predicts failures, recommends optimizations, detects
risks, and generates executive reports — all while remaining fully
observable and auditable.

Components:
  - models: HealthScore, Forecast, Optimization, Risk, Capacity, Report
  - executive_engine: 12 health dimensions + enterprise score
  - engines: PredictiveAnalytics + Optimization + Risk + Capacity + Cost
  - digital_twin: Real-time system model + graph
  - reporting: Daily/weekly/monthly/reliability/optimization/risk/mission reports
  - manager: IntelligenceManager facade

Integration (backward-compatible):
  - Reads from MissionManager, LearningEngine, ResourceManager
  - No changes to existing runtime — pure read-only extension
  - Never auto-applies optimizations — recommendations only
"""

from __future__ import annotations

from services.intelligence.digital_twin import DigitalTwinEngine
from services.intelligence.engines import (
    CapacityPlanningEngine,
    CostIntelligenceEngine,
    OptimizationEngine,
    PredictiveAnalyticsEngine,
    RiskAnalysisEngine,
)
from services.intelligence.executive_engine import ExecutiveIntelligenceEngine
from services.intelligence.manager import IntelligenceManager
from services.intelligence.models import (
    CapacityForecast,
    ComponentHealth,
    CostBreakdown,
    CostForecast,
    DigitalTwinNode,
    DigitalTwinSnapshot,
    EnterpriseHealthScore,
    ForecastConfidence,
    ForecastResult,
    ForecastType,
    HealthDimension,
    IntelligenceReport,
    IntelligenceReportType,
    OperationalMetrics,
    OptimizationRecommendation,
    OptimizationType,
    RiskAssessment,
    RiskLevel,
    RiskType,
)
from services.intelligence.reporting import ReportingEngine

__all__ = [
    "CapacityForecast",
    "CapacityPlanningEngine",
    "ComponentHealth",
    "CostBreakdown",
    "CostForecast",
    "CostIntelligenceEngine",
    "DigitalTwinEngine",
    "DigitalTwinNode",
    "DigitalTwinSnapshot",
    "EnterpriseHealthScore",
    "ExecutiveIntelligenceEngine",
    "ForecastConfidence",
    "ForecastResult",
    "ForecastType",
    "HealthDimension",
    "IntelligenceManager",
    "IntelligenceReport",
    "IntelligenceReportType",
    "OperationalMetrics",
    "OptimizationEngine",
    "OptimizationRecommendation",
    "OptimizationType",
    "PredictiveAnalyticsEngine",
    "ReportingEngine",
    "RiskAnalysisEngine",
    "RiskAssessment",
    "RiskLevel",
    "RiskType",
]
