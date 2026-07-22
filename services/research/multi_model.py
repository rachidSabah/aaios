"""Phase 3 — Multi-Model Reasoning.

Multiple LLMs independently analyze the same question. Their reasoning is
compared, conflicts are detected, evidence is ranked, a consensus is
generated, and minority opinions are recorded. Every conclusion carries
a confidence score and an explanation.

The engine does NOT call real LLMs in tests — it accepts ``ModelAnalysis``
objects produced elsewhere (e.g. by the ModelRouter). When called without
real analyses, it produces low-confidence, transparent results that
explicitly note the absence of multi-model input.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from core.logging import get_logger
from services.research.models import (
    MinorityOpinion,
    ModelAnalysis,
    ModelReasoningResult,
)

_log = get_logger(__name__)

__all__ = ["MultiModelReasoningEngine"]


class MultiModelReasoningEngine:
    """Phase 3 — Multi-Model Reasoning.

    Accepts independent analyses from multiple LLMs and produces a
    consensus result with conflicts, minority opinions, evidence ranking,
    and explainability metadata.
    """

    # --- public API -----------------------------------------------------

    async def reason(
        self,
        question: str,
        analyses: list[ModelAnalysis],
        *,
        min_models_for_consensus: int = 2,
    ) -> ModelReasoningResult:
        """Produce a multi-model reasoning result.

        Args:
            question: The question being analyzed.
            analyses: Independent analyses from multiple models.
            min_models_for_consensus: Minimum number of models required
                to attempt consensus. Below this, the result carries an
                explicit low-confidence warning.
        """
        valid = [a for a in analyses if not a.error]
        conflicts = self._detect_conflicts(valid)
        consensus, consensus_confidence = self._build_consensus(
            question, valid, conflicts, min_models_for_consensus
        )
        minority_opinions = self._extract_minority_opinions(valid, consensus)
        evidence_ranking = self._rank_evidence(valid)
        explanation = self._build_explanation(
            question, len(valid), len(conflicts), len(minority_opinions), consensus_confidence
        )
        result = ModelReasoningResult(
            question=question,
            analyses=analyses,
            consensus=consensus,
            consensus_confidence=consensus_confidence,
            conflicts=conflicts,
            minority_opinions=minority_opinions,
            evidence_ranking=evidence_ranking,
            explanation=explanation,
            requires_approval=True,
        )
        _log.info(
            "research.multi_model_reasoning_completed",
            question=question[:80],
            models=len(valid),
            conflicts=len(conflicts),
            minority_opinions=len(minority_opinions),
            confidence=consensus_confidence,
        )
        return result

    # --- conflict detection --------------------------------------------

    def _detect_conflicts(self, analyses: list[ModelAnalysis]) -> list[dict[str, Any]]:
        """Detect conflicts between model analyses.

        A conflict is recorded when two models make claims about the same
        entity / topic that disagree in polarity or numerical value.
        """
        conflicts: list[dict[str, Any]] = []
        if len(analyses) < 2:
            return conflicts
        # Extract (model, claim) pairs
        all_claims: list[tuple[str, str]] = []
        for a in analyses:
            for claim in a.claims:
                all_claims.append((a.model, claim))
        # Compare claims pairwise for negation patterns
        for i, (m1, c1) in enumerate(all_claims):
            for m2, c2 in all_claims[i + 1 :]:
                if m1 == m2:
                    continue
                conflict_kind = self._claims_conflict(c1, c2)
                if conflict_kind:
                    conflicts.append(
                        {
                            "model_a": m1,
                            "claim_a": c1,
                            "model_b": m2,
                            "claim_b": c2,
                            "conflict_type": conflict_kind,
                            "explanation": f"Models disagree: '{c1[:80]}' vs '{c2[:80]}'.",
                        }
                    )
        return conflicts

    def _claims_conflict(self, c1: str, c2: str) -> str | None:
        """Heuristic conflict detection between two claims."""
        # Negation conflict (check both directions)
        for a, b in ((c1, c2), (c2, c1)):
            negated = re.search(
                r"\b(not|no|never|cannot|cannot|doesn't|isn't|wasn't|won't)\b", a, re.I
            )
            if negated:
                a_stripped = re.sub(
                    r"\s*\b(not|no|never|cannot|cannot|doesn't|isn't|wasn't|won't)\b\s*",
                    " ",
                    a,
                    flags=re.I,
                )
                a_stripped = re.sub(r"\s+", " ", a_stripped).strip()
                if a_stripped and a_stripped.lower() in b.lower():
                    return "negation"
        # Numerical disagreement
        nums1 = re.findall(r"-?\d+(?:\.\d+)?", c1)
        nums2 = re.findall(r"-?\d+(?:\.\d+)?", c2)
        if nums1 and nums2:
            # If both claims mention numbers and they differ on the same metric
            for n1 in nums1:
                for n2 in nums2:
                    try:
                        if abs(float(n1) - float(n2)) > 0.01 and self._same_topic(c1, c2):
                            return "numerical_disagreement"
                    except ValueError:
                        continue
        return None

    def _same_topic(self, c1: str, c2: str) -> bool:
        """Rough topic overlap check."""
        words1 = {w.lower() for w in re.findall(r"\b\w{4,}\b", c1)}
        words2 = {w.lower() for w in re.findall(r"\b\w{4,}\b", c2)}
        if not words1 or not words2:
            return False
        overlap = words1 & words2
        return len(overlap) >= 2

    # --- consensus ------------------------------------------------------

    def _build_consensus(
        self,
        question: str,
        analyses: list[ModelAnalysis],
        conflicts: list[dict[str, Any]],
        min_models: int,
    ) -> tuple[str, float]:
        """Build a consensus statement and confidence."""
        if not analyses:
            return (
                f"No model analyses available for the question: '{question[:80]}'. "
                "Consensus cannot be formed.",
                0.0,
            )
        if len(analyses) < min_models:
            return (
                f"Only {len(analyses)} model analysis available — consensus requires at least "
                f"{min_models}. Primary view: {analyses[0].response[:200]}",
                analyses[0].confidence * 0.5,
            )
        # Aggregate claims via majority vote
        all_claims: list[str] = []
        for a in analyses:
            all_claims.extend(a.claims)
        if not all_claims:
            # Fall back to responses
            return self._build_consensus_from_responses(analyses, conflicts)
        # Find the most common claims (frequency-weighted)
        claim_counts = Counter(all_claims)
        top_claims = claim_counts.most_common(3)
        agreement_ratio = sum(c for _, c in top_claims) / max(1, len(all_claims))
        confidence = min(1.0, agreement_ratio * 0.7 + 0.2)
        if conflicts:
            confidence *= max(0.3, 1.0 - len(conflicts) * 0.15)
        consensus_text = f"Consensus across {len(analyses)} models: " + "; ".join(
            claim for claim, _ in top_claims
        )
        if conflicts:
            consensus_text += f" (with {len(conflicts)} conflict(s) noted)."
        return consensus_text, round(confidence, 4)

    def _build_consensus_from_responses(
        self, analyses: list[ModelAnalysis], conflicts: list[dict[str, Any]]
    ) -> tuple[str, float]:
        """Build consensus from free-text responses when no claims are structured."""
        responses = [a.response for a in analyses if a.response]
        if not responses:
            return "No substantive responses from any model.", 0.0
        # Use the longest response as primary
        primary = max(responses, key=len)
        confidence = sum(a.confidence for a in analyses) / len(analyses)
        if conflicts:
            confidence *= 0.7
        return (
            f"Consensus (response-based): {primary[:300]}...",
            round(min(1.0, confidence), 4),
        )

    # --- minority opinions ---------------------------------------------

    def _extract_minority_opinions(
        self, analyses: list[ModelAnalysis], consensus: str
    ) -> list[MinorityOpinion]:
        """Identify analyses that dissent from the consensus."""
        if len(analyses) < 2:
            return []
        minority: list[MinorityOpinion] = []
        # Compute the average confidence — models well below average are candidates
        if not analyses:
            return minority
        avg_conf = sum(a.confidence for a in analyses) / len(analyses)
        consensus_words = {w.lower() for w in re.findall(r"\b\w{5,}\b", consensus)}
        for a in analyses:
            # Does the analysis use substantially different vocabulary?
            response_words = {w.lower() for w in re.findall(r"\b\w{5,}\b", a.response)}
            if not response_words:
                continue
            overlap = consensus_words & response_words
            overlap_ratio = len(overlap) / max(1, len(response_words))
            if overlap_ratio < 0.3 or a.confidence < avg_conf * 0.7:
                # Find the most distinctive claim
                claim = a.claims[0] if a.claims else a.response[:200]
                minority.append(
                    MinorityOpinion(
                        model=a.model,
                        provider=a.provider,
                        claim=claim,
                        rationale=a.reasoning or a.response[:300],
                        evidence=[
                            f"model_confidence={a.confidence:.2f}",
                            f"overlap_ratio={overlap_ratio:.2f}",
                        ],
                        confidence=a.confidence,
                        disagreement_reason=(
                            "low_vocabulary_overlap"
                            if overlap_ratio < 0.3
                            else "low_confidence_relative_to_peers"
                        ),
                    )
                )
        return minority

    # --- evidence ranking ----------------------------------------------

    def _rank_evidence(self, analyses: list[ModelAnalysis]) -> list[dict[str, Any]]:
        """Rank evidence by confidence and provider reliability."""
        evidence_items: list[dict[str, Any]] = []
        for a in analyses:
            if a.error:
                continue
            for claim in a.claims:
                evidence_items.append(
                    {
                        "claim": claim,
                        "model": a.model,
                        "provider": a.provider,
                        "confidence": a.confidence,
                        "evidence_strength": self._evidence_strength(a),
                    }
                )
        # Sort by evidence_strength descending
        evidence_items.sort(key=lambda x: x["evidence_strength"], reverse=True)
        return evidence_items[:20]

    def _evidence_strength(self, analysis: ModelAnalysis) -> float:
        """Compute a 0..1 evidence strength score for an analysis."""
        # Weight: confidence 60%, claim count 20%, no-error 20%
        claim_factor = min(1.0, len(analysis.claims) * 0.2)
        error_factor = 1.0 if not analysis.error else 0.0
        return round(analysis.confidence * 0.6 + claim_factor * 0.2 + error_factor * 0.2, 4)

    # --- explanation ----------------------------------------------------

    def _build_explanation(
        self,
        question: str,
        model_count: int,
        conflict_count: int,
        minority_count: int,
        confidence: float,
    ) -> str:
        """Build a human-readable explanation of the reasoning process."""
        parts: list[str] = [
            f"Multi-model reasoning on: '{question[:80]}'",
            f"Models consulted: {model_count}",
            f"Conflicts detected: {conflict_count}",
            f"Minority opinions: {minority_count}",
            f"Final confidence: {confidence:.2f}",
        ]
        if confidence < 0.3:
            parts.append(
                "WARNING: Low confidence — gather additional model analyses or evidence before relying on this conclusion."
            )
        elif confidence < 0.6:
            parts.append(
                "CAUTION: Moderate confidence — verify with additional sources before publication."
            )
        else:
            parts.append(
                "Confidence is sufficient for internal use; human review still required for publication."
            )
        return ". ".join(parts) + "."
