"""Executive Decision Engine — evidence-based decisions during mission execution.

The Executive Layer continuously evaluates the mission state and decides:
  - Should this mission start/pause/resume/cancel?
  - Should it be replanned?
  - Should tasks merge or split?
  - Should another provider/agent be selected?
  - Should approval be requested?
  - Should memory/research/reflection occur?
  - Should execution continue?

Every decision is evidence-based — the engine collects evidence from the
mission state, budget, quality metrics, risk register, and historical
experience (via the LearningEngine), then applies rules to reach a
decision with recorded reasoning.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.organization.models import (
    ApprovalStatus,
    Decision,
    DecisionType,
    ExecutiveRole,
    Mission,
    MissionStatus,
    RiskSeverity,
    WBSNode,
)
from services.organization.state_machine import MissionStateMachine

_log = get_logger(__name__)

__all__ = [
    "DecisionContext",
    "DecisionEngine",
    "DecisionEvidence",
    "DecisionRecommendation",
]


from dataclasses import dataclass, field  # noqa: E402


@dataclass
class DecisionEvidence:
    """Evidence collected to support a decision."""

    mission_status: str = ""
    completion_pct: float = 0.0
    budget_utilization_pct: float = 0.0
    budget_over: bool = False
    deadline_approaching: bool = False
    deadline_passed: bool = False
    quality_score: float = 0.0
    quality_below_threshold: bool = False
    high_risk_count: int = 0
    failed_task_count: int = 0
    in_progress_task_count: int = 0
    blocked_task_count: int = 0
    pending_approval_count: int = 0
    agent_failure_rate: float = 0.0
    provider_failure_rate: float = 0.0
    recent_replan_count: int = 0
    time_since_start_s: float = 0.0
    elapsed_vs_estimated_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_status": self.mission_status,
            "completion_pct": round(self.completion_pct, 2),
            "budget_utilization_pct": round(self.budget_utilization_pct, 2),
            "budget_over": self.budget_over,
            "deadline_approaching": self.deadline_approaching,
            "deadline_passed": self.deadline_passed,
            "quality_score": round(self.quality_score, 4),
            "quality_below_threshold": self.quality_below_threshold,
            "high_risk_count": self.high_risk_count,
            "failed_task_count": self.failed_task_count,
            "in_progress_task_count": self.in_progress_task_count,
            "blocked_task_count": self.blocked_task_count,
            "pending_approval_count": self.pending_approval_count,
            "agent_failure_rate": round(self.agent_failure_rate, 4),
            "provider_failure_rate": round(self.provider_failure_rate, 4),
            "recent_replan_count": self.recent_replan_count,
            "time_since_start_s": round(self.time_since_start_s, 2),
            "elapsed_vs_estimated_ratio": round(self.elapsed_vs_estimated_ratio, 4),
        }


@dataclass
class DecisionRecommendation:
    """A decision recommendation from the engine."""

    decision_type: str
    should_act: bool
    confidence: float  # 0.0-1.0
    reasoning: str
    evidence: dict[str, Any] = field(default_factory=dict)
    recommended_action: str | None = None
    affected_node_ids: list[str] = field(default_factory=list)
    urgency: str = "normal"  # low, normal, high, critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "should_act": self.should_act,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "evidence": dict(self.evidence),
            "recommended_action": self.recommended_action,
            "affected_node_ids": list(self.affected_node_ids),
            "urgency": self.urgency,
        }


class DecisionContext:
    """Context for a decision — the mission + optional external data."""

    def __init__(
        self,
        mission: Mission,
        *,
        learning_engine: Any | None = None,
        agent_registry: Any | None = None,
    ) -> None:
        self.mission = mission
        self.learning_engine = learning_engine
        self.agent_registry = agent_registry


class DecisionEngine:
    """Makes evidence-based executive decisions during mission execution.

    The engine is stateless — it evaluates the current mission state and
    returns recommendations. The MissionManager is responsible for
    executing the recommendations and recording the decisions.
    """

    # Thresholds (configurable in production via config)
    QUALITY_THRESHOLD = 0.6
    BUDGET_ALERT_PCT = 80.0
    DEADLINE_APPROACHING_HOURS = 24.0
    HIGH_RISK_THRESHOLD = 0.7
    FAILURE_RATE_THRESHOLD = 0.3
    MAX_REPLANS_BEFORE_ESCALATION = 3

    def __init__(self, state_machine: MissionStateMachine | None = None) -> None:
        self._state_machine = state_machine or MissionStateMachine()

    def collect_evidence(self, mission: Mission) -> DecisionEvidence:
        """Collect all evidence relevant to decision-making."""
        total_nodes = len(mission.wbs_nodes)
        completed = sum(1 for n in mission.wbs_nodes if n.status == "succeeded")
        failed = sum(1 for n in mission.wbs_nodes if n.status == "failed")
        in_progress = sum(1 for n in mission.wbs_nodes if n.status == "running")
        blocked = sum(1 for n in mission.wbs_nodes if n.status == "blocked")
        pending_approvals = sum(
            1 for g in mission.approval_gates if g.status == ApprovalStatus.PENDING.value
        )

        completion_pct = (completed / total_nodes * 100) if total_nodes > 0 else 0.0
        budget_util = mission.budget.utilization_pct
        quality_score = mission.quality.composite_score

        # Deadline analysis
        deadline_approaching = False
        deadline_passed = False
        if mission.deadline:
            now = datetime.now(UTC)
            time_remaining = (mission.deadline - now).total_seconds()
            deadline_approaching = 0 < time_remaining < self.DEADLINE_APPROACHING_HOURS * 3600
            deadline_passed = time_remaining <= 0

        # Risk analysis
        high_risk_count = sum(
            1
            for r in mission.risks
            if r.status == "open" and r.risk_score >= self.HIGH_RISK_THRESHOLD
        )

        # Agent/provider failure rates (from mission decisions history)
        agent_failures = sum(
            1 for d in mission.decisions if d.decision_type == DecisionType.SWITCH_AGENT.value
        )
        provider_failures = sum(
            1 for d in mission.decisions if d.decision_type == DecisionType.SWITCH_PROVIDER.value
        )
        total_assignments = max(1, len(mission.wbs_nodes))
        agent_failure_rate = agent_failures / total_assignments
        provider_failure_rate = provider_failures / total_assignments

        recent_replans = sum(
            1 for d in mission.decisions if d.decision_type == DecisionType.REPLAN.value
        )

        time_since_start = mission.elapsed_s()
        estimated_total = sum(n.estimated_duration_s for n in mission.wbs_nodes)
        elapsed_vs_estimated = time_since_start / estimated_total if estimated_total > 0 else 0.0

        return DecisionEvidence(
            mission_status=mission.status,
            completion_pct=completion_pct,
            budget_utilization_pct=budget_util,
            budget_over=mission.budget.is_over_budget,
            deadline_approaching=deadline_approaching,
            deadline_passed=deadline_passed,
            quality_score=quality_score,
            quality_below_threshold=quality_score < self.QUALITY_THRESHOLD,
            high_risk_count=high_risk_count,
            failed_task_count=failed,
            in_progress_task_count=in_progress,
            blocked_task_count=blocked,
            pending_approval_count=pending_approvals,
            agent_failure_rate=agent_failure_rate,
            provider_failure_rate=provider_failure_rate,
            recent_replan_count=recent_replans,
            time_since_start_s=time_since_start,
            elapsed_vs_estimated_ratio=elapsed_vs_estimated,
        )

    def evaluate(self, mission: Mission) -> list[DecisionRecommendation]:
        """Evaluate the mission and return all applicable recommendations.

        Returns a list of recommendations sorted by urgency (critical first).
        The MissionManager decides which to execute.
        """
        evidence = self.collect_evidence(mission)
        recommendations: list[DecisionRecommendation] = []

        # Rule 1: Budget over → pause + escalate
        if evidence.budget_over:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.PAUSE.value,
                    should_act=True,
                    confidence=0.95,
                    reasoning=f"Mission is over budget (utilization: {evidence.budget_utilization_pct:.1f}%). "
                    "Pausing to prevent further spend until budget is reviewed.",
                    evidence=evidence.to_dict(),
                    recommended_action="pause_mission",
                    urgency="critical",
                )
            )

        # Rule 2: Deadline passed → fail or replan
        if evidence.deadline_passed and mission.status == MissionStatus.EXECUTING.value:
            if evidence.recent_replan_count >= self.MAX_REPLANS_BEFORE_ESCALATION:
                recommendations.append(
                    DecisionRecommendation(
                        decision_type=DecisionType.CANCEL.value,
                        should_act=True,
                        confidence=0.9,
                        reasoning=f"Deadline passed and {evidence.recent_replan_count} replans already attempted. "
                        "Cancelling to stop further resource consumption.",
                        evidence=evidence.to_dict(),
                        recommended_action="cancel_mission",
                        urgency="critical",
                    )
                )
            else:
                recommendations.append(
                    DecisionRecommendation(
                        decision_type=DecisionType.REPLAN.value,
                        should_act=True,
                        confidence=0.85,
                        reasoning="Deadline passed. Replanning to prioritize remaining deliverables.",
                        evidence=evidence.to_dict(),
                        recommended_action="replan_mission",
                        urgency="critical",
                    )
                )

        # Rule 3: Deadline approaching + low completion → escalate
        if evidence.deadline_approaching and evidence.completion_pct < 50.0:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.REQUEST_APPROVAL.value,
                    should_act=True,
                    confidence=0.8,
                    reasoning=f"Deadline approaching in <24h but only {evidence.completion_pct:.1f}% complete. "
                    "Requesting approval for deadline extension or scope reduction.",
                    evidence=evidence.to_dict(),
                    recommended_action="request_deadline_extension",
                    urgency="high",
                )
            )

        # Rule 4: Quality below threshold → reflect + rework
        if evidence.quality_below_threshold and evidence.quality_score > 0:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.REFLECT.value,
                    should_act=True,
                    confidence=0.75,
                    reasoning=f"Quality score {evidence.quality_score:.2f} is below threshold {self.QUALITY_THRESHOLD}. "
                    "Triggering reflection to identify quality issues.",
                    evidence=evidence.to_dict(),
                    recommended_action="trigger_reflection",
                    urgency="high",
                )
            )

        # Rule 5: High failure rate → switch agent or provider
        if evidence.agent_failure_rate > self.FAILURE_RATE_THRESHOLD:
            failing_nodes = [
                n.node_id for n in mission.wbs_nodes if n.status == "failed" and n.assigned_agent_id
            ]
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.SWITCH_AGENT.value,
                    should_act=True,
                    confidence=0.8,
                    reasoning=f"Agent failure rate {evidence.agent_failure_rate:.1%} exceeds threshold "
                    f"{self.FAILURE_RATE_THRESHOLD:.0%}. Switching to alternative agent.",
                    evidence=evidence.to_dict(),
                    recommended_action="switch_agent",
                    affected_node_ids=failing_nodes,
                    urgency="high",
                )
            )

        if evidence.provider_failure_rate > self.FAILURE_RATE_THRESHOLD:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.SWITCH_PROVIDER.value,
                    should_act=True,
                    confidence=0.8,
                    reasoning=f"Provider failure rate {evidence.provider_failure_rate:.1%} exceeds threshold "
                    f"{self.FAILURE_RATE_THRESHOLD:.0%}. Switching to alternative provider.",
                    evidence=evidence.to_dict(),
                    recommended_action="switch_provider",
                    urgency="high",
                )
            )

        # Rule 6: Blocked tasks → replan or research
        if evidence.blocked_task_count > 0:
            blocked_nodes = [n.node_id for n in mission.wbs_nodes if n.status == "blocked"]
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.RESEARCH.value,
                    should_act=True,
                    confidence=0.7,
                    reasoning=f"{evidence.blocked_task_count} tasks are blocked. "
                    "Researching alternative approaches or unblocking strategies.",
                    evidence=evidence.to_dict(),
                    recommended_action="research_unblock",
                    affected_node_ids=blocked_nodes,
                    urgency="normal",
                )
            )

        # Rule 7: High risk materializing → pause + mitigate
        materialized_risks = [
            r
            for r in mission.risks
            if r.status == "materialized"
            and r.severity
            in (
                RiskSeverity.CRITICAL.value,
                RiskSeverity.HIGH.value,
            )
        ]
        if materialized_risks:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.PAUSE.value,
                    should_act=True,
                    confidence=0.9,
                    reasoning=f"{len(materialized_risks)} high-severity risks have materialized. "
                    "Pausing mission to implement mitigations.",
                    evidence=evidence.to_dict(),
                    recommended_action="pause_for_risk_mitigation",
                    urgency="critical",
                )
            )

        # Rule 8: Pending approvals → request
        if evidence.pending_approval_count > 0:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.REQUEST_APPROVAL.value,
                    should_act=True,
                    confidence=0.6,
                    reasoning=f"{evidence.pending_approval_count} approval gates are pending. "
                    "Notifying approvers.",
                    evidence=evidence.to_dict(),
                    recommended_action="notify_approvers",
                    urgency="normal",
                )
            )

        # Rule 9: Everything looks good → continue
        if not recommendations:
            recommendations.append(
                DecisionRecommendation(
                    decision_type=DecisionType.CONTINUE.value,
                    should_act=True,
                    confidence=0.9,
                    reasoning="No issues detected. Mission is progressing normally. Continue execution.",
                    evidence=evidence.to_dict(),
                    recommended_action="continue_execution",
                    urgency="low",
                )
            )

        # Sort by urgency
        urgency_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        recommendations.sort(key=lambda r: urgency_order.get(r.urgency, 99))
        return recommendations

    def make_decision(
        self,
        mission: Mission,
        recommendation: DecisionRecommendation,
        *,
        actor: str = ExecutiveRole.MISSION_SUPERVISOR.value,
    ) -> Decision:
        """Convert a recommendation into a recorded decision."""
        decision = Decision(
            mission_id=mission.mission_id,
            decision_type=recommendation.decision_type,
            made_by=actor,
            reasoning=recommendation.reasoning,
            evidence=recommendation.evidence,
            action_taken=recommendation.recommended_action,
            affected_wbs_node_ids=recommendation.affected_node_ids,
        )
        mission.decisions.append(decision)
        _log.info(
            "Decision for mission %s: %s (confidence=%.2f, urgency=%s)",
            mission.mission_id,
            decision.decision_type,
            recommendation.confidence,
            recommendation.urgency,
        )
        return decision

    def should_start_mission(self, mission: Mission) -> DecisionRecommendation:
        """Evaluate whether a mission should start executing."""
        errors = []
        if not mission.objectives:
            errors.append("No objectives defined")
        if not mission.wbs_nodes:
            errors.append("No WBS nodes — mission needs decomposition")
        if mission.budget.total_usd <= 0:
            errors.append("No budget allocated")
        # Check dependencies
        for dep_id in mission.depends_on_missions:
            # In production, check if dependency mission is completed
            pass

        if errors:
            return DecisionRecommendation(
                decision_type=DecisionType.START.value,
                should_act=False,
                confidence=0.9,
                reasoning="Mission is not ready: " + "; ".join(errors),
            )
        return DecisionRecommendation(
            decision_type=DecisionType.START.value,
            should_act=True,
            confidence=0.95,
            reasoning="Mission has objectives, WBS, and budget. Ready to start.",
            recommended_action="start_mission",
            urgency="normal",
        )

    def should_pause_mission(self, mission: Mission) -> DecisionRecommendation:
        """Evaluate whether a mission should be paused."""
        recs = self.evaluate(mission)
        for rec in recs:
            if rec.decision_type == DecisionType.PAUSE.value and rec.should_act:
                return rec
        return DecisionRecommendation(
            decision_type=DecisionType.PAUSE.value,
            should_act=False,
            confidence=0.9,
            reasoning="No pause conditions met.",
        )

    def should_cancel_mission(self, mission: Mission) -> DecisionRecommendation:
        """Evaluate whether a mission should be cancelled."""
        recs = self.evaluate(mission)
        for rec in recs:
            if rec.decision_type == DecisionType.CANCEL.value and rec.should_act:
                return rec
        return DecisionRecommendation(
            decision_type=DecisionType.CANCEL.value,
            should_act=False,
            confidence=0.9,
            reasoning="No cancel conditions met.",
        )

    def should_replan_mission(self, mission: Mission) -> DecisionRecommendation:
        """Evaluate whether a mission should be replanned."""
        recs = self.evaluate(mission)
        for rec in recs:
            if rec.decision_type == DecisionType.REPLAN.value and rec.should_act:
                return rec
        return DecisionRecommendation(
            decision_type=DecisionType.REPLAN.value,
            should_act=False,
            confidence=0.9,
            reasoning="No replan conditions met.",
        )

    def select_provider_for_task(
        self,
        mission: Mission,
        node: WBSNode,
        *,
        available_providers: list[str] | None = None,
    ) -> DecisionRecommendation:
        """Recommend a provider for a WBS node based on history + cost."""
        # If the node already has a provider assigned, keep it unless it's failing
        if (
            node.assigned_provider
            and available_providers
            and node.assigned_provider in available_providers
        ):
            return DecisionRecommendation(
                decision_type=DecisionType.SWITCH_PROVIDER.value,
                should_act=False,
                confidence=0.8,
                reasoning=f"Provider '{node.assigned_provider}' already assigned and available.",
                affected_node_ids=[node.node_id],
            )
        # Pick the first available provider (in production, consult LearningEngine)
        if available_providers:
            chosen = available_providers[0]
            return DecisionRecommendation(
                decision_type=DecisionType.SWITCH_PROVIDER.value,
                should_act=True,
                confidence=0.7,
                reasoning=f"Assigning provider '{chosen}' to task '{node.title}'.",
                recommended_action=f"assign_provider:{chosen}",
                affected_node_ids=[node.node_id],
            )
        return DecisionRecommendation(
            decision_type=DecisionType.SWITCH_PROVIDER.value,
            should_act=False,
            confidence=0.5,
            reasoning="No providers available.",
            affected_node_ids=[node.node_id],
        )

    def select_agent_for_task(
        self,
        mission: Mission,
        node: WBSNode,
        *,
        available_agents: list[str] | None = None,
    ) -> DecisionRecommendation:
        """Recommend an agent for a WBS node based on capabilities + history."""
        if (
            node.assigned_agent_id
            and available_agents
            and node.assigned_agent_id in available_agents
        ):
            return DecisionRecommendation(
                decision_type=DecisionType.SWITCH_AGENT.value,
                should_act=False,
                confidence=0.8,
                reasoning=f"Agent '{node.assigned_agent_id}' already assigned and available.",
                affected_node_ids=[node.node_id],
            )
        if available_agents:
            chosen = available_agents[0]
            return DecisionRecommendation(
                decision_type=DecisionType.SWITCH_AGENT.value,
                should_act=True,
                confidence=0.7,
                reasoning=f"Assigning agent '{chosen}' to task '{node.title}'.",
                recommended_action=f"assign_agent:{chosen}",
                affected_node_ids=[node.node_id],
            )
        return DecisionRecommendation(
            decision_type=DecisionType.SWITCH_AGENT.value,
            should_act=False,
            confidence=0.5,
            reasoning="No agents available.",
            affected_node_ids=[node.node_id],
        )
