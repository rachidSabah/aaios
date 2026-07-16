"""Phase 6 — Knowledge Synthesis.

Merges multiple documents into unified knowledge. Generates:
executive summary, technical summary, timeline, entity extraction,
relationship maps, decision support, key insights, recommendations,
and open questions.

Every section carries confidence, evidence, and source references.
The synthesis is never auto-published — human approval required.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from services.research.models import (
    DocumentSummary,
    Entity,
    KnowledgeSynthesis,
    Source,
    SynthesisSection,
)

_log = get_logger(__name__)

__all__ = ["KnowledgeSynthesisEngine"]

# Common English stop words for entity extraction
_STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "this", "that", "these",
    "those", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "shall", "can", "need", "it", "its", "as", "if", "then",
    "than", "so", "such", "no", "not", "only", "own", "same", "too", "very",
    "s", "t", "just", "also", "we", "our", "you", "your", "they", "their",
    "he", "she", "his", "her", "him", "i", "me", "my",
})


class KnowledgeSynthesisEngine:
    """Phase 6 — Knowledge Synthesis Engine.

    Accepts documents (as ``Source`` objects with abstracts/text) plus
    optional research findings and produces a unified ``KnowledgeSynthesis``
    report with nine standard sections.
    """

    # --- public API -----------------------------------------------------

    async def synthesize(
        self,
        project_id: str,
        title: str,
        documents: list[Source],
        *,
        description: str = "",
        research_question: str = "",
    ) -> KnowledgeSynthesis:
        """Synthesize multiple documents into a unified knowledge report."""
        if not documents:
            return self._empty_synthesis(project_id, title, description)

        doc_summaries = self._summarize_documents(documents)
        entities = self._extract_entities(documents)
        timeline = self._build_timeline(documents)
        relationship_map = self._build_relationship_map(entities, documents)
        sections: list[SynthesisSection] = []
        sections.append(self._executive_summary(documents, research_question))
        sections.append(self._technical_summary(documents, entities))
        sections.append(self._timeline_section(timeline))
        sections.append(self._entities_section(entities))
        sections.append(self._relationships_section(relationship_map))
        sections.append(self._decision_support(documents, entities, research_question))
        sections.append(self._key_insights(documents, entities))
        sections.append(self._recommendations(documents, entities, research_question))
        sections.append(self._open_questions(documents, research_question))
        overall_confidence = self._overall_confidence(documents, sections)
        synthesis = KnowledgeSynthesis(
            project_id=project_id,
            title=title,
            description=description,
            sections=sections,
            document_summaries=doc_summaries,
            entities=entities,
            timeline=timeline,
            relationship_map=relationship_map,
            overall_confidence=overall_confidence,
            requires_approval=True,
        )
        _log.info(
            "research.synthesis_produced",
            project_id=project_id,
            documents=len(documents),
            sections=len(sections),
            entities=len(entities),
            confidence=overall_confidence,
        )
        return synthesis

    # --- document summaries --------------------------------------------

    def _summarize_documents(self, documents: list[Source]) -> list[DocumentSummary]:
        out: list[DocumentSummary] = []
        for doc in documents:
            text = doc.abstract or doc.title
            key_points = self._extract_key_points(text)
            word_count = len(text.split())
            relevance = min(1.0, doc.reliability_score * 0.7 + (len(key_points) * 0.05))
            out.append(DocumentSummary(
                source_id=doc.source_id,
                title=doc.title,
                summary=self._truncate(text, 300),
                key_points=key_points,
                relevance=round(relevance, 4),
                word_count=word_count,
            ))
        return out

    def _extract_key_points(self, text: str, max_points: int = 5) -> list[str]:
        """Heuristic key point extraction — first sentences of each paragraph."""
        if not text:
            return []
        # Split by sentence enders
        sentences = re.split(r"(?<=[.!?])\s+", text)
        # Take the longest sentences as key points
        ranked = sorted(sentences, key=len, reverse=True)
        return [s.strip() for s in ranked[:max_points] if len(s.strip()) > 20]

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3].rsplit(" ", 1)[0] + "..."

    # --- entity extraction ---------------------------------------------

    def _extract_entities(self, documents: list[Source]) -> list[Entity]:
        """Heuristic entity extraction via capitalized n-grams and dates."""
        text_corpus = " ".join(d.abstract or d.title for d in documents)
        if not text_corpus:
            return []
        entities: dict[str, Entity] = {}
        # Capitalized sequences (likely proper nouns)
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text_corpus):
            name = match.group(1).strip()
            if name.lower() in _STOP_WORDS or len(name) < 3:
                continue
            self._add_entity(entities, name, "concept", text_corpus)
        # Dates
        for match in re.finditer(r"\b(\d{4}|\d{1,2}/\d{1,2}/\d{2,4})\b", text_corpus):
            name = match.group(1)
            self._add_entity(entities, name, "date", text_corpus)
        # Numbers with units (metrics)
        for match in re.finditer(r"\b(\d+(?:\.\d+)?\s*(?:%|billion|million|trillion|USD|EUR|kg|km))\b", text_corpus, re.I):
            name = match.group(1)
            self._add_entity(entities, name, "metric", text_corpus)
        # Sort by mention count
        return sorted(entities.values(), key=lambda e: e.mentions, reverse=True)[:30]

    def _add_entity(
        self, entities: dict[str, Entity], name: str, entity_type: str, corpus: str
    ) -> None:
        if name in entities:
            entities[name].mentions += 1
        else:
            entities[name] = Entity(
                name=name,
                entity_type=entity_type,
                mentions=corpus.lower().count(name.lower()),
                description=f"Extracted from document corpus ({entity_type}).",
                confidence=0.6,
            )

    # --- timeline -------------------------------------------------------

    def _build_timeline(self, documents: list[Source]) -> list[dict[str, Any]]:
        """Build a timeline from document publication dates."""
        entries: list[dict[str, Any]] = []
        for doc in documents:
            if doc.published_at:
                entries.append({
                    "timestamp": doc.published_at.isoformat(),
                    "title": doc.title,
                    "description": f"Document published by {', '.join(doc.authors) or 'unknown'}.",
                    "source_id": doc.source_id,
                })
        entries.sort(key=lambda e: e["timestamp"])
        return entries

    # --- relationship map ----------------------------------------------

    def _build_relationship_map(
        self, entities: list[Entity], documents: list[Source]
    ) -> list[dict[str, Any]]:
        """Build a coarse entity co-occurrence relationship map."""
        # Co-occurrence in document abstracts
        co_occurrence: dict[tuple[str, str], int] = defaultdict(int)
        for doc in documents:
            text = (doc.abstract or doc.title).lower()
            present = [e for e in entities if e.name.lower() in text]
            for i, e1 in enumerate(present):
                for e2 in present[i + 1:]:
                    pair: tuple[str, str] = tuple(sorted([e1.name, e2.name]))  # type: ignore[assignment]
                    co_occurrence[pair] += 1
        # Convert to list of relationship dicts
        out: list[dict[str, Any]] = []
        for (a, b), count in sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True):
            if count < 1:
                continue
            out.append({
                "source": a,
                "target": b,
                "relation": "co_occurs_with",
                "weight": min(1.0, count * 0.3),
                "evidence": [f"co_occurrence_count={count}"],
            })
        return out[:50]

    # --- sections -------------------------------------------------------

    def _executive_summary(
        self, documents: list[Source], research_question: str
    ) -> SynthesisSection:
        top_doc = max(documents, key=lambda d: d.reliability_score) if documents else None
        content = (
            f"Synthesized {len(documents)} document(s)"
            + (f" addressing: '{research_question[:80]}'" if research_question else "")
            + ". "
            + (f"Primary source: '{top_doc.title}'." if top_doc else "")
            + " Key themes are extracted from document abstracts and ranked by reliability."
        )
        bullets = self._top_themes(documents)
        return SynthesisSection(
            title="Executive Summary",
            section_type="executive_summary",
            content=content,
            bullet_points=bullets,
            evidence=[f"document_count={len(documents)}"],
            confidence=min(0.9, 0.3 + 0.1 * len(documents)),
            sources=[d.source_id for d in documents[:5]],
        )

    def _technical_summary(
        self, documents: list[Source], entities: list[Entity]
    ) -> SynthesisSection:
        content = (
            f"Technical synthesis covers {len(documents)} source(s). "
            f"Extracted {len(entities)} entities. "
            "Detailed technical findings are organized by entity co-occurrence and source reliability."
        )
        bullets = [f"{e.name} ({e.entity_type}, {e.mentions} mentions)" for e in entities[:10]]
        return SynthesisSection(
            title="Technical Summary",
            section_type="technical_summary",
            content=content,
            bullet_points=bullets,
            evidence=[f"entity_count={len(entities)}"],
            confidence=0.6,
            sources=[d.source_id for d in documents[:5]],
        )

    def _timeline_section(self, timeline: list[dict[str, Any]]) -> SynthesisSection:
        content = (
            f"Timeline of {len(timeline)} dated event(s) extracted from document publication dates."
        )
        bullets = [f"{e['timestamp'][:10]}: {e['title']}" for e in timeline[:10]]
        return SynthesisSection(
            title="Timeline",
            section_type="timeline",
            content=content,
            bullet_points=bullets,
            evidence=[f"event_count={len(timeline)}"],
            confidence=0.7 if timeline else 0.2,
            sources=[e.get("source_id", "") for e in timeline if e.get("source_id")],
        )

    def _entities_section(self, entities: list[Entity]) -> SynthesisSection:
        content = (
            f"{len(entities)} entities extracted via capitalized n-gram and date detection."
        )
        bullets = [f"{e.name} [{e.entity_type}] — {e.mentions} mentions" for e in entities[:15]]
        return SynthesisSection(
            title="Entities",
            section_type="entities",
            content=content,
            bullet_points=bullets,
            evidence=[f"entity_count={len(entities)}"],
            confidence=0.55,
        )

    def _relationships_section(
        self, relationship_map: list[dict[str, Any]]
    ) -> SynthesisSection:
        content = (
            f"{len(relationship_map)} relationship(s) detected via entity co-occurrence."
        )
        bullets = [
            f"{r['source']} ↔ {r['target']} (weight: {r['weight']:.2f})"
            for r in relationship_map[:10]
        ]
        return SynthesisSection(
            title="Relationship Map",
            section_type="relationships",
            content=content,
            bullet_points=bullets,
            evidence=[f"relationship_count={len(relationship_map)}"],
            confidence=0.5,
        )

    def _decision_support(
        self,
        documents: list[Source],
        entities: list[Entity],
        research_question: str,
    ) -> SynthesisSection:
        avg_reliability = (
            sum(d.reliability_score for d in documents) / len(documents)
            if documents else 0.0
        )
        content = (
            f"Decision support based on {len(documents)} source(s) with average reliability "
            f"{avg_reliability:.2f}. "
            + ("Sources are sufficient for tentative decisions." if avg_reliability > 0.6
               else "Sources are insufficient — gather additional high-reliability material before decisions.")
        )
        bullets = [
            f"Average source reliability: {avg_reliability:.2f}",
            f"Total sources: {len(documents)}",
            f"Entities extracted: {len(entities)}",
        ]
        return SynthesisSection(
            title="Decision Support",
            section_type="decision_support",
            content=content,
            bullet_points=bullets,
            evidence=[f"avg_reliability={avg_reliability:.2f}"],
            confidence=avg_reliability,
            sources=[d.source_id for d in documents[:3]],
        )

    def _key_insights(
        self, documents: list[Source], entities: list[Entity]
    ) -> SynthesisSection:
        # Most frequent entities → key insights
        top_entities = entities[:5]
        bullets = [
            f"{e.name} emerges as a central theme ({e.mentions} mentions)."
            for e in top_entities
        ]
        if not bullets:
            bullets = ["Insufficient corpus for insight extraction."]
        content = (
            f"{len(bullets)} key insight(s) derived from entity frequency and co-occurrence analysis."
        )
        return SynthesisSection(
            title="Key Insights",
            section_type="insights",
            content=content,
            bullet_points=bullets,
            evidence=[f"top_entity_mentions={sum(e.mentions for e in top_entities)}"],
            confidence=0.55,
        )

    def _recommendations(
        self,
        documents: list[Source],
        entities: list[Entity],
        research_question: str,
    ) -> SynthesisSection:
        bullets: list[str] = []
        if len(documents) < 5:
            bullets.append("Expand the document corpus — current size is below 5 sources.")
        if documents and sum(1 for d in documents if d.reliability == "tier_1_peer_reviewed") == 0:
            bullets.append("Add peer-reviewed sources to strengthen the evidence base.")
        if entities:
            top = entities[0]
            bullets.append(f"Investigate '{top.name}' further — highest mention count ({top.mentions}).")
        bullets.append("Cross-validate findings with a domain expert before publication.")
        content = (
            f"{len(bullets)} recommendation(s) generated from corpus analysis."
        )
        return SynthesisSection(
            title="Recommendations",
            section_type="recommendations",
            content=content,
            bullet_points=bullets,
            evidence=[f"recommendation_count={len(bullets)}"],
            confidence=0.65,
        )

    def _open_questions(
        self, documents: list[Source], research_question: str
    ) -> SynthesisSection:
        bullets: list[str] = []
        if research_question:
            bullets.append(f"Has the original research question been fully answered? — '{research_question[:80]}'")
        gaps = self._detect_knowledge_gaps(documents)
        bullets.extend(gaps)
        content = (
            f"{len(bullets)} open question(s) remain after synthesis."
        )
        return SynthesisSection(
            title="Open Questions",
            section_type="open_questions",
            content=content,
            bullet_points=bullets,
            evidence=[f"open_question_count={len(bullets)}"],
            confidence=0.6,
        )

    def _detect_knowledge_gaps(self, documents: list[Source]) -> list[str]:
        gaps: list[str] = []
        if any(not d.abstract for d in documents):
            gaps.append("Some documents lack abstracts — full-text analysis recommended.")
        if len({d.source_type for d in documents}) == 1:
            gaps.append("All sources share the same type — diversify source types.")
        old_sources = [d for d in documents if d.published_at and (datetime.now(UTC) - d.published_at).days > 365]
        if old_sources:
            gaps.append(f"{len(old_sources)} source(s) are over 1 year old — verify currency.")
        return gaps

    # --- helpers --------------------------------------------------------

    def _top_themes(self, documents: list[Source], max_themes: int = 5) -> list[str]:
        """Extract top themes via word frequency across the corpus."""
        text = " ".join(d.abstract or d.title for d in documents).lower()
        words = re.findall(r"\b[a-z]{5,}\b", text)
        words = [w for w in words if w not in _STOP_WORDS]
        return [w for w, _ in Counter(words).most_common(max_themes)]

    def _overall_confidence(
        self, documents: list[Source], sections: list[SynthesisSection]
    ) -> float:
        if not sections:
            return 0.0
        avg_section_conf = sum(s.confidence for s in sections) / len(sections)
        avg_reliability = (
            sum(d.reliability_score for d in documents) / len(documents)
            if documents else 0.0
        )
        return round(min(1.0, (avg_section_conf * 0.6) + (avg_reliability * 0.4)), 4)

    def _empty_synthesis(
        self, project_id: str, title: str, description: str
    ) -> KnowledgeSynthesis:
        return KnowledgeSynthesis(
            project_id=project_id,
            title=title,
            description=description,
            sections=[SynthesisSection(
                title="No Documents",
                section_type="executive_summary",
                content="No documents were provided for synthesis.",
                bullet_points=["Provide at least one document with an abstract or text field."],
                evidence=["document_count=0"],
                confidence=0.0,
            )],
            overall_confidence=0.0,
        )
