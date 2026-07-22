"""Phase 2 — Multi-Agent Research.

Ten specialized research agents. Each agent produces structured findings
with summary, key points, evidence, sources, confidence, limitations, and
follow-up questions.

The agents are abstract — they accept a query plus optional source material
and produce structured findings. They never fabricate evidence: when source
material is unavailable, they return low-confidence findings with explicit
limitations and follow-up questions.

All agents are READ-ONLY and require human approval for any export.
"""

from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger
from services.research.models import (
    ResearchAgentFinding,
    ResearchAgentType,
    Source,
    SourceReliability,
)

_log = get_logger(__name__)

__all__ = [
    "BusinessResearchAgent",
    "FinancialResearchAgent",
    "LegalResearchAgent",
    "LiteratureAgent",
    "MarketResearchAgent",
    "NewsResearchAgent",
    "OpenDataResearchAgent",
    "PolicyResearchAgent",
    "ResearchAgentBase",
    "ResearchAgentOrganization",
    "ScientificResearchAgent",
    "TechnologyResearchAgent",
]


class ResearchAgentBase:
    """Base class for all research agents.

    Subclasses implement ``_analyze`` which receives the query, source
    material, and options, and returns a list of key points plus evidence.
    """

    agent_type: ResearchAgentType = ResearchAgentType.LITERATURE
    display_name: str = "Research Agent"
    description: str = "Base research agent."
    default_reliability: SourceReliability = SourceReliability.TIER_3_ESTABLISHED

    async def research(
        self,
        query: str,
        *,
        session_id: str = "",
        source_material: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> ResearchAgentFinding:
        """Run research and produce a structured finding."""
        opts = options or {}
        materials = source_material or []
        key_points, evidence, sources, limitations, follow_ups = await self._analyze(
            query, materials, opts
        )
        confidence = self._compute_confidence(len(sources), len(evidence), len(limitations))
        finding = ResearchAgentFinding(
            session_id=session_id,
            agent_type=self.agent_type.value,
            title=self._build_title(query),
            summary=self._build_summary(query, key_points, len(sources)),
            key_points=key_points,
            evidence=evidence,
            sources=sources,
            confidence=confidence,
            limitations=limitations,
            follow_up_questions=follow_ups,
            metadata={
                "agent_display_name": self.display_name,
                "source_count": len(sources),
                "options": opts,
            },
        )
        _log.info(
            "research.agent_finding_produced",
            agent=self.agent_type.value,
            query=query[:80],
            confidence=confidence,
            sources=len(sources),
        )
        return finding

    # --- to override ----------------------------------------------------

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        """Return (key_points, evidence, sources, limitations, follow_ups)."""
        raise NotImplementedError

    # --- helpers --------------------------------------------------------

    def _build_title(self, query: str) -> str:
        clean = re.sub(r"\s+", " ", query).strip()
        if len(clean) > 80:
            clean = clean[:77] + "..."
        return f"{self.display_name}: {clean}"

    def _build_summary(self, query: str, key_points: list[str], source_count: int) -> str:
        if not key_points:
            return (
                f"No findings produced for query '{query[:80]}' by {self.display_name}. "
                f"Source material was {'present' if source_count else 'absent'}."
            )
        head = key_points[0] if key_points else ""
        return (
            f"{self.display_name} analyzed '{query[:80]}' across {source_count} source(s). "
            f"Primary finding: {head[:200]}"
        )

    def _compute_confidence(
        self, source_count: int, evidence_count: int, limitation_count: int
    ) -> float:
        """Compute confidence in [0, 1] from coverage and limitations."""
        base = 0.2
        base += min(0.4, source_count * 0.1)
        base += min(0.25, evidence_count * 0.05)
        base -= min(0.3, limitation_count * 0.1)
        return max(0.0, min(1.0, base))

    def _source_from_material(self, item: dict[str, Any]) -> Source:
        return Source(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source_type=item.get("source_type", ""),
            authors=item.get("authors", []),
            published_at=item.get("published_at"),
            reliability=item.get("reliability", self.default_reliability.value),
            reliability_score=float(item.get("reliability_score", 0.5)),
            citation_count=int(item.get("citation_count", 0)),
            abstract=item.get("abstract", ""),
            doi=item.get("doi", ""),
            isbn=item.get("isbn", ""),
        )

    def _extract_evidence(self, materials: list[dict[str, Any]]) -> list[str]:
        evidence: list[str] = []
        for m in materials:
            text = m.get("abstract") or m.get("text") or m.get("summary") or ""
            if text:
                # Take first 200 chars as evidence snippet
                snippet = re.sub(r"\s+", " ", text).strip()[:200]
                if snippet:
                    evidence.append(f"[{m.get('title', 'unknown')}] {snippet}")
        return evidence


# ---------------------------------------------------------------------------
# The ten specialized research agents
# ---------------------------------------------------------------------------


class LiteratureAgent(ResearchAgentBase):
    """Literature research agent — books, essays, literary criticism."""

    agent_type = ResearchAgentType.LITERATURE
    display_name = "Literature Research Agent"
    description = "Researches books, essays, literary criticism, and authorship."
    default_reliability = SourceReliability.TIER_3_ESTABLISHED

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            title = m.get("title", "")
            author = ", ".join(m.get("authors", [])) or "unknown"
            year = ""
            if m.get("published_at"):
                try:
                    year = (
                        str(m["published_at"].year)
                        if hasattr(m["published_at"], "year")
                        else str(m["published_at"])[:4]
                    )
                except (AttributeError, TypeError, ValueError):
                    year = ""
            if title:
                key_points.append(f"{author} ({year}): {title}")
        if not source_material:
            key_points.append(
                "No literature source material provided — query requires targeted retrieval."
            )
        limitations = []
        if not source_material:
            limitations.append(
                "No source material supplied — findings are based on agent capabilities only."
            )
        follow_ups = [
            f"Expand the corpus for '{query[:60]}' with primary texts and peer-reviewed criticism.",
            "Cross-reference authorship attribution across multiple scholarly indexes.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class ScientificResearchAgent(ResearchAgentBase):
    """Scientific research agent — peer-reviewed papers, datasets, replications."""

    agent_type = ResearchAgentType.SCIENTIFIC
    display_name = "Scientific Research Agent"
    description = "Researches peer-reviewed papers, datasets, replication studies."
    default_reliability = SourceReliability.TIER_1_PEER_REVIEWED

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            doi = m.get("doi", "")
            title = m.get("title", "")
            if doi and title:
                key_points.append(f"DOI {doi}: {title}")
            elif title:
                key_points.append(title)
        if not source_material:
            key_points.append(
                "No scientific source material provided — query requires database retrieval (PubMed, arXiv, etc.)."
            )
        limitations: list[str] = []
        if not any(m.get("doi") for m in source_material):
            limitations.append(
                "No DOI-identified sources — verification against peer-reviewed indexes recommended."
            )
        if not source_material:
            limitations.append(
                "Empty source corpus — scientific findings require empirical grounding."
            )
        follow_ups = [
            f"Retrieve peer-reviewed papers matching '{query[:60]}' from established indexes.",
            "Check for replication studies and meta-analyses.",
            "Assess sample sizes and statistical power of cited studies.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class LegalResearchAgent(ResearchAgentBase):
    """Legal research agent — statutes, case law, regulations, treaties."""

    agent_type = ResearchAgentType.LEGAL
    display_name = "Legal Research Agent"
    description = "Researches statutes, case law, regulations, and treaties."
    default_reliability = SourceReliability.TIER_2_OFFICIAL

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        jurisdiction = options.get("jurisdiction", "")
        key_points: list[str] = []
        for m in source_material:
            title = m.get("title", "")
            citation = m.get("citation", "")
            if citation:
                key_points.append(f"{citation}: {title}")
            elif title:
                key_points.append(title)
        if not source_material:
            key_points.append(
                "No legal source material provided — query requires retrieval from legal databases."
            )
        limitations: list[str] = []
        if not jurisdiction:
            limitations.append(
                "No jurisdiction specified — legal findings are jurisdiction-dependent."
            )
        if not source_material:
            limitations.append(
                "No primary legal sources supplied — verify against official gazettes and court records."
            )
        follow_ups = [
            f"Confirm jurisdiction scope for '{query[:60]}'.",
            "Check for recent amendments and pending litigation.",
            "Cross-reference with regulatory agency interpretations.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class BusinessResearchAgent(ResearchAgentBase):
    """Business research agent — companies, industries, market positioning."""

    agent_type = ResearchAgentType.BUSINESS
    display_name = "Business Research Agent"
    description = "Researches companies, industries, and business strategies."
    default_reliability = SourceReliability.TIER_3_ESTABLISHED

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            company = m.get("company") or m.get("title", "")
            industry = m.get("industry", "")
            if company and industry:
                key_points.append(f"{company} ({industry})")
            elif company:
                key_points.append(company)
        if not source_material:
            key_points.append(
                "No business source material provided — query requires SEC filings, analyst reports, etc."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append("No business sources — verify financial filings independently.")
        follow_ups = [
            f"Retrieve latest 10-K / annual report for companies in '{query[:60]}'.",
            "Cross-reference analyst consensus and peer benchmarks.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class TechnologyResearchAgent(ResearchAgentBase):
    """Technology research agent — specifications, RFCs, technical documentation."""

    agent_type = ResearchAgentType.TECHNOLOGY
    display_name = "Technology Research Agent"
    description = "Researches technical specs, RFCs, standards, and implementations."
    default_reliability = SourceReliability.TIER_2_OFFICIAL

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            spec = m.get("spec") or m.get("title", "")
            version = m.get("version", "")
            if spec and version:
                key_points.append(f"{spec} v{version}")
            elif spec:
                key_points.append(spec)
        if not source_material:
            key_points.append(
                "No technical source material provided — query requires retrieval of RFCs, specs, and docs."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append(
                "No primary technical specifications — verify against standards bodies."
            )
        follow_ups = [
            f"Identify authoritative specification for '{query[:60]}'.",
            "Check for deprecation notices and successor specs.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class MarketResearchAgent(ResearchAgentBase):
    """Market research agent — market size, segments, trends, forecasts."""

    agent_type = ResearchAgentType.MARKET
    display_name = "Market Research Agent"
    description = "Researches market size, segments, trends, and forecasts."
    default_reliability = SourceReliability.TIER_3_ESTABLISHED

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            market = m.get("market") or m.get("title", "")
            size = m.get("size", "")
            if market and size:
                key_points.append(f"{market}: {size}")
            elif market:
                key_points.append(market)
        if not source_material:
            key_points.append(
                "No market source material provided — query requires analyst reports and trade data."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append("No market sizing data — figures require independent verification.")
        follow_ups = [
            f"Retrieve market sizing and CAGR forecasts for '{query[:60]}'.",
            "Cross-reference multiple analyst sources for triangulation.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class NewsResearchAgent(ResearchAgentBase):
    """News research agent — current events, press releases, journalism."""

    agent_type = ResearchAgentType.NEWS
    display_name = "News Research Agent"
    description = "Researches current events, press releases, and journalism."
    default_reliability = SourceReliability.TIER_3_ESTABLISHED

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            headline = m.get("title", "")
            outlet = m.get("outlet") or (
                m.get("authors", ["unknown"])[0] if m.get("authors") else "unknown"
            )
            if headline:
                key_points.append(f"[{outlet}] {headline}")
        if not source_material:
            key_points.append(
                "No news source material provided — query requires real-time news retrieval."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append("No news sources — verify recency and outlet reliability.")
        limitations.append("News content is time-sensitive — re-verify before drawing conclusions.")
        follow_ups = [
            f"Retrieve recent (≤30 days) coverage of '{query[:60]}' from established outlets.",
            "Cross-reference wire services with original reporting.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class FinancialResearchAgent(ResearchAgentBase):
    """Financial research agent — prices, ratios, filings, macro indicators."""

    agent_type = ResearchAgentType.FINANCIAL
    display_name = "Financial Research Agent"
    description = "Researches prices, ratios, filings, and macro indicators."
    default_reliability = SourceReliability.TIER_2_OFFICIAL

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            ticker = m.get("ticker") or m.get("title", "")
            metric = m.get("metric", "")
            value = m.get("value", "")
            if ticker and metric and value:
                key_points.append(f"{ticker} {metric} = {value}")
            elif ticker:
                key_points.append(ticker)
        if not source_material:
            key_points.append(
                "No financial source material provided — query requires filings and market data feeds."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append(
                "No financial data — verify against regulatory filings and exchange feeds."
            )
        limitations.append("Financial data is point-in-time — re-verify before decisions.")
        follow_ups = [
            f"Retrieve latest SEC filings for '{query[:60]}'.",
            "Verify market data against multiple exchanges.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class PolicyResearchAgent(ResearchAgentBase):
    """Policy research agent — government policy, regulations, impact analysis."""

    agent_type = ResearchAgentType.POLICY
    display_name = "Policy Research Agent"
    description = "Researches government policy, regulations, and impact analysis."
    default_reliability = SourceReliability.TIER_2_OFFICIAL

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            title = m.get("title", "")
            agency = m.get("agency", "")
            if title and agency:
                key_points.append(f"[{agency}] {title}")
            elif title:
                key_points.append(title)
        if not source_material:
            key_points.append(
                "No policy source material provided — query requires government gazettes and agency publications."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append(
                "No primary policy documents — verify against official government sources."
            )
        follow_ups = [
            f"Identify responsible agencies for '{query[:60]}'.",
            "Check for public consultation periods and stakeholder submissions.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


class OpenDataResearchAgent(ResearchAgentBase):
    """Open data research agent — public datasets, statistics, government data."""

    agent_type = ResearchAgentType.OPEN_DATA
    display_name = "Open Data Research Agent"
    description = "Researches public datasets, statistics, and government open data."
    default_reliability = SourceReliability.TIER_2_OFFICIAL

    async def _analyze(
        self,
        query: str,
        source_material: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[Source], list[str], list[str]]:
        sources = [self._source_from_material(m) for m in source_material]
        evidence = self._extract_evidence(source_material)
        key_points: list[str] = []
        for m in source_material:
            dataset = m.get("dataset") or m.get("title", "")
            publisher = m.get("publisher", "")
            if dataset and publisher:
                key_points.append(f"[{publisher}] {dataset}")
            elif dataset:
                key_points.append(dataset)
        if not source_material:
            key_points.append(
                "No open-data source material provided — query requires retrieval from data portals."
            )
        limitations: list[str] = []
        if not source_material:
            limitations.append(
                "No datasets supplied — verify against official statistical agencies."
            )
        follow_ups = [
            f"Search data.gov / EU Open Data Portal / UN Data for '{query[:60]}'.",
            "Validate dataset methodology and collection period.",
        ]
        return key_points, evidence, sources, limitations, follow_ups


# ---------------------------------------------------------------------------
# Registry / organization
# ---------------------------------------------------------------------------


class ResearchAgentOrganization:
    """Registry of the ten specialized research agents."""

    def __init__(self) -> None:
        self._agents: dict[str, ResearchAgentBase] = {
            ResearchAgentType.LITERATURE.value: LiteratureAgent(),
            ResearchAgentType.SCIENTIFIC.value: ScientificResearchAgent(),
            ResearchAgentType.LEGAL.value: LegalResearchAgent(),
            ResearchAgentType.BUSINESS.value: BusinessResearchAgent(),
            ResearchAgentType.TECHNOLOGY.value: TechnologyResearchAgent(),
            ResearchAgentType.MARKET.value: MarketResearchAgent(),
            ResearchAgentType.NEWS.value: NewsResearchAgent(),
            ResearchAgentType.FINANCIAL.value: FinancialResearchAgent(),
            ResearchAgentType.POLICY.value: PolicyResearchAgent(),
            ResearchAgentType.OPEN_DATA.value: OpenDataResearchAgent(),
        }

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_type": a.agent_type.value,
                "display_name": a.display_name,
                "description": a.description,
                "default_reliability": a.default_reliability.value,
            }
            for a in self._agents.values()
        ]

    def get_agent(self, agent_type: str) -> ResearchAgentBase | None:
        return self._agents.get(agent_type)

    def select_for_query(self, query: str) -> ResearchAgentBase | None:
        """Heuristic agent selection based on query keywords."""
        q = query.lower()
        scores: dict[str, int] = dict.fromkeys(self._agents, 0)
        keyword_map = {
            ResearchAgentType.LITERATURE.value: [
                "book",
                "novel",
                "author",
                "poem",
                "essay",
                "literature",
            ],
            ResearchAgentType.SCIENTIFIC.value: [
                "study",
                "research",
                "experiment",
                "peer-review",
                "journal",
                "hypothesis",
            ],
            ResearchAgentType.LEGAL.value: [
                "law",
                "statute",
                "court",
                "case",
                "regulation",
                "treaty",
                "legal",
            ],
            ResearchAgentType.BUSINESS.value: [
                "company",
                "corporation",
                "industry",
                "business",
                "strategy",
            ],
            ResearchAgentType.TECHNOLOGY.value: [
                "technology",
                "spec",
                "rfc",
                "standard",
                "technical",
                "protocol",
            ],
            ResearchAgentType.MARKET.value: [
                "market",
                "size",
                "share",
                "cagr",
                "forecast",
                "segment",
            ],
            ResearchAgentType.NEWS.value: [
                "news",
                "headline",
                "press",
                "current",
                "today",
                "breaking",
            ],
            ResearchAgentType.FINANCIAL.value: [
                "stock",
                "price",
                "earnings",
                "financial",
                "ratio",
                "sec filing",
            ],
            ResearchAgentType.POLICY.value: [
                "policy",
                "government",
                "regulation",
                "agency",
                "public sector",
            ],
            ResearchAgentType.OPEN_DATA.value: [
                "dataset",
                "statistics",
                "open data",
                "census",
                "official statistics",
            ],
        }
        for at, keywords in keyword_map.items():
            for kw in keywords:
                if kw in q:
                    scores[at] += 1
        best = max(scores, key=lambda k: scores[k])
        if scores[best] == 0:
            return None
        return self._agents[best]

    async def research_with_all(
        self,
        query: str,
        *,
        source_material: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[ResearchAgentFinding]:
        """Run every agent against the query — used for broad exploration."""
        findings: list[ResearchAgentFinding] = []
        for agent in self._agents.values():
            finding = await agent.research(query, source_material=source_material, options=options)
            findings.append(finding)
        return findings
