"""Phase 5 — Fact Verification.

Cross-references multiple sources to verify a fact. Detects conflicting
claims, ranks source reliability, and produces a verification report
with confidence, evidence, source ranking, and verification timestamp.

Every verification requires human approval before being published.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.research.models import (
    Claim,
    Fact,
    FactVerificationReport,
    Source,
    SourceReliability,
    VerificationStatus,
)

_log = get_logger(__name__)

__all__ = ["FactVerificationEngine"]

# Reliability tier weights (0..1)
_TIER_WEIGHTS: dict[str, float] = {
    SourceReliability.TIER_1_PEER_REVIEWED.value: 0.95,
    SourceReliability.TIER_2_OFFICIAL.value: 0.85,
    SourceReliability.TIER_3_ESTABLISHED.value: 0.70,
    SourceReliability.TIER_4_COMMUNITY.value: 0.45,
    SourceReliability.TIER_5_UNVERIFIED.value: 0.20,
}


class FactVerificationEngine:
    """Phase 5 — Fact Verification Engine.

    Verifies a fact claim against a corpus of sources. The engine is
    conservative: when sources disagree, it marks the fact as
    ``contradicted`` or ``partially_verified`` rather than picking a side.
    """

    # --- public API -----------------------------------------------------

    async def verify(
        self,
        fact_text: str,
        sources: list[Source],
        *,
        verifier: str = "fact-verification-engine",
    ) -> FactVerificationReport:
        """Verify a fact against the given sources."""
        if not sources:
            return self._unverifiable_report(fact_text, verifier)
        # Classify each source's stance
        stances: list[dict[str, Any]] = []
        for src in sources:
            stance = self._classify_stance(fact_text, src)
            stances.append({
                "source_id": src.source_id,
                "source_title": src.title,
                "reliability": src.reliability,
                "reliability_score": src.reliability_score,
                "stance": stance,  # supports | contradicts | neutral
                "weight": _TIER_WEIGHTS.get(src.reliability, 0.3) * src.reliability_score,
            })
        supporting = [s for s in stances if s["stance"] == "supports"]
        contradicting = [s for s in stances if s["stance"] == "contradicts"]
        neutral = [s for s in stances if s["stance"] == "neutral"]
        status = self._compute_status(len(supporting), len(contradicting), len(neutral))
        confidence = self._compute_confidence(supporting, contradicting)
        conflicts = self._build_conflicts(supporting, contradicting)
        ranking = self._rank_sources(stances)
        explanation = self._build_explanation(
            fact_text, status, confidence, len(supporting), len(contradicting), len(neutral)
        )
        report = FactVerificationReport(
            fact_text=fact_text,
            status=status,
            confidence=confidence,
            sources_checked=len(sources),
            sources_supporting=len(supporting),
            sources_contradicting=len(contradicting),
            sources_neutral=len(neutral),
            source_ranking=ranking,
            conflicts=conflicts,
            explanation=explanation,
            verified_at=datetime.now(UTC),
            requires_approval=True,
        )
        _log.info(
            "research.fact_verified",
            fact=fact_text[:80],
            status=status,
            confidence=confidence,
            sources=len(sources),
        )
        return report

    async def verify_claim(
        self,
        claim: Claim,
        sources: list[Source],
    ) -> tuple[Fact, FactVerificationReport]:
        """Verify a Claim and produce a Fact + VerificationReport."""
        report = await self.verify(claim.text, sources)
        fact = Fact(
            text=claim.text,
            verified=(report.status == VerificationStatus.VERIFIED.value),
            verification_status=report.status,
            confidence=report.confidence,
            evidence=[f"verified_at={report.verified_at.isoformat()}"],
            sources=[s.source_id for s in sources],
            verified_at=report.verified_at,
            verifier=report.verifier if hasattr(report, "verifier") else "fact-verification-engine",
            project_id=claim.project_id,
        )
        return fact, report

    # --- helpers --------------------------------------------------------

    def _classify_stance(self, fact_text: str, source: Source) -> str:
        """Classify a source's stance toward the fact.

        Heuristic: checks if the source abstract contains the fact text
        or its key terms. Returns ``supports``, ``contradicts``, or ``neutral``.
        """
        if not source.abstract:
            return "neutral"
        fact_terms = {w.lower() for w in fact_text.split() if len(w) > 3}
        abstract_terms = {w.lower() for w in source.abstract.split() if len(w) > 3}
        if not fact_terms:
            return "neutral"
        overlap = fact_terms & abstract_terms
        overlap_ratio = len(overlap) / len(fact_terms)
        if overlap_ratio < 0.2:
            return "neutral"
        # Check for negation in abstract near fact terms
        abstract_lower = source.abstract.lower()
        negation_words = ["not", "no", "false", "incorrect", "wrong", "myth", "debunk"]
        has_negation = any(neg in abstract_lower for neg in negation_words)
        if has_negation and overlap_ratio > 0.4:
            return "contradicts"
        if overlap_ratio > 0.5:
            return "supports"
        return "neutral"

    def _compute_status(
        self, supporting: int, contradicting: int, neutral: int
    ) -> str:
        total = supporting + contradicting + neutral
        if total == 0:
            return VerificationStatus.UNVERIFIABLE.value
        if supporting > 0 and contradicting == 0:
            return VerificationStatus.VERIFIED.value if supporting >= 2 else VerificationStatus.PARTIALLY_VERIFIED.value
        if contradicting > 0 and supporting == 0:
            return VerificationStatus.CONTRADICTED.value
        if contradicting > 0 and supporting > 0:
            return VerificationStatus.PARTIALLY_VERIFIED.value if supporting > contradicting else VerificationStatus.CONTRADICTED.value
        return VerificationStatus.UNVERIFIED.value

    def _compute_confidence(
        self,
        supporting: list[dict[str, Any]],
        contradicting: list[dict[str, Any]],
    ) -> float:
        if not supporting and not contradicting:
            return 0.0
        support_weight = sum(s["weight"] for s in supporting)
        contra_weight = sum(c["weight"] for c in contradicting)
        total = support_weight + contra_weight
        if total == 0:
            return 0.0
        confidence: float = (support_weight - contra_weight) / total
        # Scale by number of supporting sources (more sources → higher confidence)
        confidence *= min(1.0, 0.5 + 0.1 * len(supporting))
        return round(max(0.0, min(1.0, float(confidence))), 4)

    def _build_conflicts(
        self,
        supporting: list[dict[str, Any]],
        contradicting: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not contradicting:
            return []
        return [
            {
                "supporting_sources": [s["source_id"] for s in supporting],
                "contradicting_sources": [c["source_id"] for c in contradicting],
                "explanation": (
                    f"{len(supporting)} source(s) support vs "
                    f"{len(contradicting)} source(s) contradict."
                ),
            }
        ]

    def _rank_sources(self, stances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank sources by reliability tier and stance certainty."""
        return sorted(stances, key=lambda s: s["weight"], reverse=True)

    def _build_explanation(
        self,
        fact_text: str,
        status: str,
        confidence: float,
        supporting: int,
        contradicting: int,
        neutral: int,
    ) -> str:
        return (
            f"Fact '{fact_text[:80]}' verification: status={status}, "
            f"confidence={confidence:.2f}. "
            f"Sources: {supporting} supporting, {contradicting} contradicting, {neutral} neutral. "
            f"Verification methodology: term-overlap stance classification with reliability weighting."
        )

    def _unverifiable_report(self, fact_text: str, verifier: str) -> FactVerificationReport:
        return FactVerificationReport(
            fact_text=fact_text,
            status=VerificationStatus.UNVERIFIABLE.value,
            confidence=0.0,
            sources_checked=0,
            sources_supporting=0,
            sources_contradicting=0,
            sources_neutral=0,
            source_ranking=[],
            conflicts=[],
            explanation=(
                f"No sources provided for fact '{fact_text[:80]}'. "
                "Fact cannot be verified without source material."
            ),
            verified_at=datetime.now(UTC),
            requires_approval=True,
        )
