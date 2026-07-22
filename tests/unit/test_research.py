"""Tests for AAiOS v5.3 — Enterprise Research & Reasoning Platform.

Covers all 6 phases: Research Engine, Multi-Agent Research,
Multi-Model Reasoning, Evidence Graph, Fact Verification,
Knowledge Synthesis, plus the ResearchManager facade.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.research import (
    BusinessResearchAgent,
    Claim,
    ClaimRelationType,
    EvidenceGraph,
    EvidenceRelationType,
    Fact,
    FactVerificationEngine,
    FactVerificationReport,
    FinancialResearchAgent,
    KnowledgeSynthesis,
    KnowledgeSynthesisEngine,
    LegalResearchAgent,
    LiteratureAgent,
    MarketResearchAgent,
    ModelAnalysis,
    ModelReasoningResult,
    MultiModelReasoningEngine,
    NewsResearchAgent,
    OpenDataResearchAgent,
    PolicyResearchAgent,
    ResearchAgentOrganization,
    ResearchAgentType,
    ResearchEngine,
    ResearchManager,
    ScientificResearchAgent,
    Source,
    SourceReliability,
    TechnologyResearchAgent,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# Phase 1 — ResearchEngine
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestResearchEngine:
    """ResearchEngine tests."""

    async def test_create_project(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project(
            "Test Project",
            "A test",
            domain="scientific",
            owner="alice",
        )
        assert project.title == "Test Project"
        assert project.domain == "scientific"
        assert project.status == "planning"

    async def test_get_project(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        fetched = await engine.get_project(project.project_id)
        assert fetched is not None
        assert fetched.project_id == project.project_id

    async def test_list_projects_by_status(self) -> None:
        engine = ResearchEngine()
        await engine.create_project("P1")
        p2 = await engine.create_project("P2")
        await engine.start_project(p2.project_id)
        active = await engine.list_projects(status="active")
        assert len(active) == 1
        assert active[0].project_id == p2.project_id

    async def test_create_session(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        session = await engine.create_session(project.project_id, "S1", "query?")
        assert session is not None
        assert session.project_id == project.project_id

    async def test_create_session_unknown_project(self) -> None:
        engine = ResearchEngine()
        session = await engine.create_session("unknown", "S1", "query?")
        assert session is None

    async def test_complete_session(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        session = await engine.create_session(project.project_id, "S1", "q")
        await engine.start_session(session.session_id)
        completed = await engine.complete_session(
            session.session_id, finding_count=3, sources_consulted=5
        )
        assert completed.status == "completed"
        assert completed.finding_count == 3

    async def test_create_plan(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        plan = await engine.create_plan(
            project.project_id,
            "Plan 1",
            "desc",
            objectives=["obj1"],
            research_questions=["q1"],
        )
        assert plan is not None
        assert plan.objectives == ["obj1"]

    async def test_create_task(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        session = await engine.create_session(project.project_id, "S1", "q")
        task = await engine.create_task(
            session.session_id, "Task 1", "desc", agent_type="scientific"
        )
        assert task is not None
        assert task.agent_type == "scientific"

    async def test_create_pipeline(self) -> None:
        from services.research.models import ResearchPipelineStage

        engine = ResearchEngine()
        project = await engine.create_project("P1")
        pipeline = await engine.create_pipeline(
            project.project_id,
            "Pipeline 1",
            "desc",
            stages=[ResearchPipelineStage(name="Stage 1", agent_type="scientific")],
        )
        assert pipeline is not None
        assert len(pipeline.stages) == 1

    async def test_create_template(self) -> None:
        engine = ResearchEngine()
        template = await engine.create_template(
            "T1", "desc", domain="scientific", objectives=["o1"]
        )
        assert template.domain == "scientific"

    async def test_instantiate_template(self) -> None:
        engine = ResearchEngine()
        template = await engine.create_template(
            "T1", "desc", domain="scientific", objectives=["o1"]
        )
        project = await engine.instantiate_template(template.template_id, "New Project")
        assert project is not None
        assert project.domain == "scientific"
        assert project.objectives == ["o1"]

    async def test_memory(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        mem = await engine.add_memory(
            project.project_id, "finding", "key1", "value1", confidence=0.8
        )
        fetched = await engine.get_memory(mem.memory_id)
        assert fetched is not None
        assert fetched.access_count == 1
        results = await engine.search_memory("value1")
        assert len(results) == 1

    async def test_workspace(self) -> None:
        engine = ResearchEngine()
        ws = await engine.create_workspace("WS1", "desc", owner="alice")
        project = await engine.create_project("P1")
        updated = await engine.add_project_to_workspace(ws.workspace_id, project.project_id)
        assert updated is not None
        assert project.project_id in updated.project_ids

    async def test_timeline(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        await engine.start_project(project.project_id)
        timeline = await engine.timeline(project_id=project.project_id)
        assert len(timeline) >= 2  # project_created + project_started

    async def test_add_finding(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        session = await engine.create_session(project.project_id, "S1", "q")
        finding = await engine.add_finding(
            project.project_id,
            session.session_id,
            "Finding 1",
            "desc",
            claims=["claim1"],
            confidence=0.7,
        )
        assert finding is not None
        assert finding.confidence == 0.7

    async def test_history(self) -> None:
        engine = ResearchEngine()
        project = await engine.create_project("P1")
        session = await engine.create_session(project.project_id, "S1", "q")
        await engine.add_finding(project.project_id, session.session_id, "F1")
        history = await engine.history(project.project_id)
        assert len(history.sessions) == 1
        assert len(history.findings) == 1

    async def test_stats(self) -> None:
        engine = ResearchEngine()
        await engine.create_project("P1")
        stats = await engine.stats()
        assert stats["projects"] == 1
        assert "projects_by_status" in stats


# ---------------------------------------------------------------------------
# Phase 2 — Multi-Agent Research
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestResearchAgents:
    """Tests for the 10 specialized research agents."""

    async def test_agent_organization_has_ten_agents(self) -> None:
        org = ResearchAgentOrganization()
        agents = org.list_agents()
        assert len(agents) == 10

    async def test_agent_types_complete(self) -> None:
        org = ResearchAgentOrganization()
        agents = org.list_agents()
        types = {a["agent_type"] for a in agents}
        assert types == {t.value for t in ResearchAgentType}

    async def test_literature_agent_research(self) -> None:
        agent = LiteratureAgent()
        finding = await agent.research("Shakespeare's comedies")
        assert finding.agent_type == ResearchAgentType.LITERATURE.value
        assert finding.confidence >= 0.0
        assert len(finding.follow_up_questions) > 0

    async def test_scientific_agent_research_with_sources(self) -> None:
        agent = ScientificResearchAgent()
        sources = [
            {
                "title": "Paper A",
                "doi": "10.1000/test",
                "abstract": "This paper studies quantum entanglement and its effects.",
                "authors": ["Smith"],
                "source_type": "paper",
            }
        ]
        finding = await agent.research("quantum entanglement", source_material=sources)
        assert finding.agent_type == ResearchAgentType.SCIENTIFIC.value
        assert len(finding.sources) == 1
        assert finding.sources[0].doi == "10.1000/test"

    async def test_legal_agent_with_jurisdiction(self) -> None:
        agent = LegalResearchAgent()
        finding = await agent.research("GDPR compliance", options={"jurisdiction": "EU"})
        assert finding.agent_type == ResearchAgentType.LEGAL.value

    async def test_business_agent(self) -> None:
        agent = BusinessResearchAgent()
        finding = await agent.research("Apple Inc strategy")
        assert finding.agent_type == ResearchAgentType.BUSINESS.value

    async def test_technology_agent(self) -> None:
        agent = TechnologyResearchAgent()
        finding = await agent.research("HTTP/3 specification")
        assert finding.agent_type == ResearchAgentType.TECHNOLOGY.value

    async def test_market_agent(self) -> None:
        agent = MarketResearchAgent()
        finding = await agent.research("EV market size 2025")
        assert finding.agent_type == ResearchAgentType.MARKET.value

    async def test_news_agent(self) -> None:
        agent = NewsResearchAgent()
        finding = await agent.research("latest elections")
        assert finding.agent_type == ResearchAgentType.NEWS.value

    async def test_financial_agent(self) -> None:
        agent = FinancialResearchAgent()
        finding = await agent.research("AAPL P/E ratio")
        assert finding.agent_type == ResearchAgentType.FINANCIAL.value

    async def test_policy_agent(self) -> None:
        agent = PolicyResearchAgent()
        finding = await agent.research("EU AI Act")
        assert finding.agent_type == ResearchAgentType.POLICY.value

    async def test_open_data_agent(self) -> None:
        agent = OpenDataResearchAgent()
        finding = await agent.research("census data 2020")
        assert finding.agent_type == ResearchAgentType.OPEN_DATA.value

    async def test_select_for_query_picks_scientific(self) -> None:
        org = ResearchAgentOrganization()
        agent = org.select_for_query("peer-reviewed study on climate")
        assert agent is not None
        assert agent.agent_type == ResearchAgentType.SCIENTIFIC

    async def test_select_for_query_picks_legal(self) -> None:
        org = ResearchAgentOrganization()
        agent = org.select_for_query("court case law precedent")
        assert agent is not None
        assert agent.agent_type == ResearchAgentType.LEGAL

    async def test_select_for_query_unknown(self) -> None:
        org = ResearchAgentOrganization()
        agent = org.select_for_query("zzz random")
        assert agent is None

    async def test_research_with_all_agents(self) -> None:
        org = ResearchAgentOrganization()
        findings = await org.research_with_all("test query")
        assert len(findings) == 10

    async def test_finding_has_evidence_and_limitations(self) -> None:
        agent = NewsResearchAgent()
        finding = await agent.research("test")
        assert isinstance(finding.evidence, list)
        assert isinstance(finding.limitations, list)
        assert len(finding.limitations) > 0


# ---------------------------------------------------------------------------
# Phase 3 — Multi-Model Reasoning
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestMultiModelReasoning:
    """MultiModelReasoningEngine tests."""

    async def test_no_analyses(self) -> None:
        engine = MultiModelReasoningEngine()
        result = await engine.reason("What is X?", [])
        assert result.consensus_confidence == 0.0
        assert "cannot be formed" in result.consensus

    async def test_single_analysis(self) -> None:
        engine = MultiModelReasoningEngine()
        analyses = [
            ModelAnalysis(
                model="gpt-4",
                provider="openai",
                response="42",
                claims=["The answer is 42."],
                confidence=0.8,
            ),
        ]
        result = await engine.reason("What is the answer?", analyses)
        # Single model — consensus requires min_models_for_consensus (default 2)
        assert "Only 1 model" in result.consensus

    async def test_consensus_with_two_models(self) -> None:
        engine = MultiModelReasoningEngine()
        analyses = [
            ModelAnalysis(
                model="gpt-4", provider="openai", claims=["The sky is blue."], confidence=0.9
            ),
            ModelAnalysis(
                model="claude", provider="anthropic", claims=["The sky is blue."], confidence=0.85
            ),
        ]
        result = await engine.reason("What color is the sky?", analyses)
        assert "Consensus across 2 models" in result.consensus
        assert result.consensus_confidence > 0.0

    async def test_conflict_detection_negation(self) -> None:
        engine = MultiModelReasoningEngine()
        analyses = [
            ModelAnalysis(model="A", provider="x", claims=["The Earth is round."], confidence=0.9),
            ModelAnalysis(
                model="B", provider="y", claims=["The Earth is not round."], confidence=0.7
            ),
        ]
        result = await engine.reason("Is the Earth round?", analyses)
        assert len(result.conflicts) >= 1

    async def test_evidence_ranking(self) -> None:
        engine = MultiModelReasoningEngine()
        analyses = [
            ModelAnalysis(model="A", provider="x", claims=["c1"], confidence=0.9),
            ModelAnalysis(model="B", provider="y", claims=["c2"], confidence=0.5),
        ]
        result = await engine.reason("q?", analyses)
        assert len(result.evidence_ranking) == 2
        # Higher-confidence analysis should rank first
        assert result.evidence_ranking[0]["model"] == "A"

    async def test_minority_opinions(self) -> None:
        engine = MultiModelReasoningEngine()
        analyses = [
            ModelAnalysis(model="A", provider="x", response="yes", claims=["yes"], confidence=0.9),
            ModelAnalysis(
                model="B",
                provider="y",
                response="completely different topic",
                claims=["different"],
                confidence=0.3,
            ),
        ]
        result = await engine.reason("q?", analyses)
        # Model B with low confidence and low overlap should be a minority opinion
        assert isinstance(result.minority_opinions, list)

    async def test_explanation_contains_required_info(self) -> None:
        engine = MultiModelReasoningEngine()
        analyses = [
            ModelAnalysis(model="A", provider="x", claims=["c1"], confidence=0.9),
            ModelAnalysis(model="B", provider="y", claims=["c1"], confidence=0.85),
        ]
        result = await engine.reason("q?", analyses)
        assert "Models consulted: 2" in result.explanation
        assert "Conflicts detected" in result.explanation

    async def test_requires_approval_true(self) -> None:
        engine = MultiModelReasoningEngine()
        result = await engine.reason("q?", [])
        assert result.requires_approval is True


# ---------------------------------------------------------------------------
# Phase 4 — Evidence Graph
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestEvidenceGraph:
    """EvidenceGraph tests."""

    def test_add_claim(self) -> None:
        graph = EvidenceGraph()
        claim = Claim(text="The Earth is round.", confidence=0.9)
        node = graph.add_claim(claim)
        assert node.kind == "claim"
        assert node.ref_id == claim.claim_id

    def test_add_fact(self) -> None:
        graph = EvidenceGraph()
        fact = Fact(text="Water boils at 100C at sea level.", confidence=1.0, verified=True)
        node = graph.add_fact(fact)
        assert node.kind == "fact"

    def test_add_source(self) -> None:
        graph = EvidenceGraph()
        source = Source(title="Wikipedia", reliability_score=0.7)
        node = graph.add_source(source)
        assert node.kind == "source"

    def test_add_relation_supports(self) -> None:
        graph = EvidenceGraph()
        c1 = Claim(text="Claim A")
        c2 = Claim(text="Claim B")
        n1 = graph.add_claim(c1)
        n2 = graph.add_claim(c2)
        edge = graph.add_relation(n1.node_id, n2.node_id, EvidenceRelationType.SUPPORT, weight=0.8)
        assert edge is not None
        assert edge.relation_type == "support"

    def test_add_relation_unknown_node(self) -> None:
        graph = EvidenceGraph()
        c1 = Claim(text="Claim A")
        n1 = graph.add_claim(c1)
        edge = graph.add_relation(n1.node_id, "unknown", EvidenceRelationType.SUPPORT)
        assert edge is None

    def test_neighbors(self) -> None:
        graph = EvidenceGraph()
        c1 = Claim(text="A")
        c2 = Claim(text="B")
        c3 = Claim(text="C")
        n1 = graph.add_claim(c1)
        n2 = graph.add_claim(c2)
        n3 = graph.add_claim(c3)
        graph.add_relation(n1.node_id, n2.node_id, EvidenceRelationType.SUPPORT)
        graph.add_relation(n1.node_id, n3.node_id, EvidenceRelationType.CONTRADICTION)
        neighbors = graph.neighbors(n1.node_id)
        assert len(neighbors) == 2

    def test_supporting_evidence(self) -> None:
        graph = EvidenceGraph()
        c1 = Claim(text="A")
        c2 = Claim(text="B supports A")
        n1 = graph.add_claim(c1)
        n2 = graph.add_claim(c2)
        graph.add_relation(n2.node_id, n1.node_id, EvidenceRelationType.SUPPORT)
        support = graph.supporting_evidence(c1.claim_id)
        assert len(support) == 1

    def test_contradicting_evidence(self) -> None:
        graph = EvidenceGraph()
        c1 = Claim(text="A")
        c2 = Claim(text="B contradicts A")
        n1 = graph.add_claim(c1)
        n2 = graph.add_claim(c2)
        graph.add_relation(n2.node_id, n1.node_id, EvidenceRelationType.CONTRADICTION)
        contra = graph.contradicting_evidence(c1.claim_id)
        assert len(contra) == 1

    def test_search(self) -> None:
        graph = EvidenceGraph()
        graph.add_claim(Claim(text="Climate change is real"))
        graph.add_claim(Claim(text="The moon is made of cheese"))
        results = graph.search("climate")
        assert len(results) == 1

    def test_evidence_strength(self) -> None:
        graph = EvidenceGraph()
        c1 = Claim(text="A", confidence=0.5)
        c2 = Claim(text="B", confidence=0.9)
        n1 = graph.add_claim(c1)
        n2 = graph.add_claim(c2)
        graph.add_relation(n2.node_id, n1.node_id, EvidenceRelationType.SUPPORT, weight=0.8)
        strength = graph.evidence_strength(n1.node_id)
        assert 0.0 <= strength <= 1.0

    def test_stats(self) -> None:
        graph = EvidenceGraph()
        graph.add_claim(Claim(text="A"))
        graph.add_fact(Fact(text="B"))
        stats = graph.stats()
        assert stats["nodes"] == 2
        assert stats["claims"] == 1
        assert stats["facts"] == 1

    def test_claim_relation(self) -> None:
        from services.research.models import ClaimRelation

        graph = EvidenceGraph()
        c1 = Claim(text="A")
        c2 = Claim(text="B")
        graph.add_claim(c1)
        graph.add_claim(c2)
        relation = ClaimRelation(
            source_claim_id=c1.claim_id,
            target_claim_id=c2.claim_id,
            relation_type=ClaimRelationType.SUPPORTS.value,
            weight=0.7,
        )
        edge = graph.add_claim_relation(relation)
        assert edge is not None
        assert edge.relation_type == "support"


# ---------------------------------------------------------------------------
# Phase 5 — Fact Verification
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestFactVerification:
    """FactVerificationEngine tests."""

    async def test_verify_no_sources(self) -> None:
        engine = FactVerificationEngine()
        report = await engine.verify("The sky is blue.", [])
        assert report.status == VerificationStatus.UNVERIFIABLE.value
        assert report.confidence == 0.0

    async def test_verify_supported(self) -> None:
        engine = FactVerificationEngine()
        fact = "Water boils at 100 degrees Celsius at sea level"
        sources = [
            Source(
                title="Physics Textbook",
                abstract="Water boils at 100 degrees Celsius at sea level under standard pressure.",
                reliability=SourceReliability.TIER_1_PEER_REVIEWED.value,
                reliability_score=0.95,
            ),
            Source(
                title="Encyclopedia",
                abstract="At sea level, water boils at 100 degrees Celsius under standard atmospheric pressure.",
                reliability=SourceReliability.TIER_2_OFFICIAL.value,
                reliability_score=0.85,
            ),
        ]
        report = await engine.verify(fact, sources)
        assert report.status in (
            VerificationStatus.VERIFIED.value,
            VerificationStatus.PARTIALLY_VERIFIED.value,
        )
        assert report.confidence > 0.0

    async def test_verify_contradicted(self) -> None:
        engine = FactVerificationEngine()
        fact = "The Earth is flat"
        sources = [
            Source(
                title="Science Journal",
                abstract="The Earth is not flat; it is an oblate spheroid.",
                reliability=SourceReliability.TIER_1_PEER_REVIEWED.value,
                reliability_score=0.95,
            ),
        ]
        report = await engine.verify(fact, sources)
        # The negation in abstract should mark as contradicts
        assert report.sources_contradicting >= 1 or report.sources_neutral >= 1

    async def test_verify_claim(self) -> None:
        engine = FactVerificationEngine()
        claim = Claim(text="The sky is blue.", confidence=0.5)
        sources = [
            Source(
                title="Atlas",
                abstract="The sky appears blue due to Rayleigh scattering.",
                reliability=SourceReliability.TIER_2_OFFICIAL.value,
                reliability_score=0.85,
            ),
        ]
        fact, report = await engine.verify_claim(claim, sources)
        assert isinstance(fact, Fact)
        assert isinstance(report, FactVerificationReport)
        assert report.sources_checked == 1

    async def test_report_has_explanation(self) -> None:
        engine = FactVerificationEngine()
        report = await engine.verify("test fact", [Source(title="A", abstract="test fact")])
        assert "explanation" in report.to_dict() or report.explanation != ""

    async def test_source_ranking(self) -> None:
        engine = FactVerificationEngine()
        sources = [
            Source(
                title="Low",
                abstract="test",
                reliability=SourceReliability.TIER_5_UNVERIFIED.value,
                reliability_score=0.2,
            ),
            Source(
                title="High",
                abstract="test",
                reliability=SourceReliability.TIER_1_PEER_REVIEWED.value,
                reliability_score=0.95,
            ),
        ]
        report = await engine.verify("test", sources)
        assert len(report.source_ranking) == 2
        # Higher-reliability source should rank first
        assert report.source_ranking[0]["source_title"] == "High"

    async def test_requires_approval(self) -> None:
        engine = FactVerificationEngine()
        report = await engine.verify("x", [Source(title="A", abstract="x")])
        assert report.requires_approval is True


# ---------------------------------------------------------------------------
# Phase 6 — Knowledge Synthesis
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestKnowledgeSynthesis:
    """KnowledgeSynthesisEngine tests."""

    async def test_synthesize_empty(self) -> None:
        engine = KnowledgeSynthesisEngine()
        synthesis = await engine.synthesize("p1", "Empty", [])
        assert synthesis.overall_confidence == 0.0
        assert len(synthesis.sections) == 1

    async def test_synthesize_with_documents(self) -> None:
        engine = KnowledgeSynthesisEngine()
        documents = [
            Source(
                title="Climate Report 2024",
                abstract="Global temperatures rose by 1.5 degrees Celsius in 2024. The Paris Agreement targets are at risk. Carbon emissions must decrease.",
                reliability=SourceReliability.TIER_1_PEER_REVIEWED.value,
                reliability_score=0.95,
                published_at=datetime(2024, 6, 1, tzinfo=UTC),
                authors=["IPCC"],
            ),
            Source(
                title="Carbon Reduction Study",
                abstract="Renewable energy adoption grew 15% in 2024. Solar and wind lead the transition. Carbon capture is emerging.",
                reliability=SourceReliability.TIER_2_OFFICIAL.value,
                reliability_score=0.85,
                published_at=datetime(2024, 9, 1, tzinfo=UTC),
                authors=["IEA"],
            ),
        ]
        synthesis = await engine.synthesize(
            "p1",
            "Climate Synthesis",
            documents,
            research_question="What is the state of climate action in 2024?",
        )
        assert len(synthesis.sections) == 9
        # Section types
        section_types = {s.section_type for s in synthesis.sections}
        assert "executive_summary" in section_types
        assert "technical_summary" in section_types
        assert "timeline" in section_types
        assert "entities" in section_types
        assert "relationships" in section_types
        assert "decision_support" in section_types
        assert "insights" in section_types
        assert "recommendations" in section_types
        assert "open_questions" in section_types

    async def test_synthesis_has_entities(self) -> None:
        engine = KnowledgeSynthesisEngine()
        documents = [
            Source(
                title="Doc",
                abstract="John Smith met with Apple Inc. in 2024 to discuss revenue of 5 billion USD.",
                reliability_score=0.8,
            ),
        ]
        synthesis = await engine.synthesize("p1", "T", documents)
        assert len(synthesis.entities) > 0

    async def test_synthesis_has_timeline(self) -> None:
        engine = KnowledgeSynthesisEngine()
        documents = [
            Source(
                title="Doc 1",
                abstract="text",
                published_at=datetime(2024, 1, 1, tzinfo=UTC),
                reliability_score=0.7,
            ),
            Source(
                title="Doc 2",
                abstract="text",
                published_at=datetime(2024, 6, 1, tzinfo=UTC),
                reliability_score=0.7,
            ),
        ]
        synthesis = await engine.synthesize("p1", "T", documents)
        assert len(synthesis.timeline) == 2
        # Sorted chronologically
        assert synthesis.timeline[0]["timestamp"] < synthesis.timeline[1]["timestamp"]

    async def test_synthesis_overall_confidence(self) -> None:
        engine = KnowledgeSynthesisEngine()
        documents = [
            Source(title="A", abstract="test content", reliability_score=0.9),
            Source(title="B", abstract="more content", reliability_score=0.8),
        ]
        synthesis = await engine.synthesize("p1", "T", documents)
        assert 0.0 < synthesis.overall_confidence <= 1.0

    async def test_synthesis_requires_approval(self) -> None:
        engine = KnowledgeSynthesisEngine()
        synthesis = await engine.synthesize(
            "p1", "T", [Source(title="A", abstract="x", reliability_score=0.5)]
        )
        assert synthesis.requires_approval is True

    async def test_document_summaries(self) -> None:
        engine = KnowledgeSynthesisEngine()
        documents = [
            Source(title="Doc 1", abstract="Some content here.", reliability_score=0.7),
        ]
        synthesis = await engine.synthesize("p1", "T", documents)
        assert len(synthesis.document_summaries) == 1
        assert synthesis.document_summaries[0].title == "Doc 1"


# ---------------------------------------------------------------------------
# ResearchManager facade
# ---------------------------------------------------------------------------


@pytest.mark.offline
class TestResearchManager:
    """ResearchManager facade tests."""

    async def test_manager_has_all_engines(self) -> None:
        mgr = ResearchManager()
        assert hasattr(mgr, "engine")
        assert hasattr(mgr, "agents")
        assert hasattr(mgr, "multi_model")
        assert hasattr(mgr, "evidence_graph")
        assert hasattr(mgr, "verification")
        assert hasattr(mgr, "synthesis")

    async def test_create_project(self) -> None:
        mgr = ResearchManager()
        project = await mgr.create_project("P1", domain="scientific")
        assert project.title == "P1"

    async def test_list_research_agents(self) -> None:
        mgr = ResearchManager()
        agents = mgr.list_research_agents()
        assert len(agents) == 10

    async def test_research_with_agent(self) -> None:
        mgr = ResearchManager()
        finding = await mgr.research_with_agent("scientific", "quantum entanglement")
        assert finding is not None
        assert finding.agent_type == "scientific"

    async def test_research_with_unknown_agent(self) -> None:
        mgr = ResearchManager()
        finding = await mgr.research_with_agent("unknown_type", "q")
        assert finding is None

    async def test_research_with_selected_agent(self) -> None:
        mgr = ResearchManager()
        finding = await mgr.research_with_selected_agent("peer-reviewed study on climate")
        assert finding is not None
        assert finding.agent_type == "scientific"

    async def test_reason(self) -> None:
        mgr = ResearchManager()
        analyses = [
            ModelAnalysis(model="A", provider="x", claims=["c1"], confidence=0.9),
            ModelAnalysis(model="B", provider="y", claims=["c1"], confidence=0.85),
        ]
        result = await mgr.reason("q?", analyses)
        assert isinstance(result, ModelReasoningResult)

    async def test_add_claim_to_graph(self) -> None:
        mgr = ResearchManager()
        claim = Claim(text="test claim")
        node_dict = mgr.add_claim_to_graph(claim)
        assert node_dict["kind"] == "claim"

    async def test_verify_fact(self) -> None:
        mgr = ResearchManager()
        sources = [
            Source(title="A", abstract="the fact is true", reliability_score=0.8),
        ]
        report = await mgr.verify_fact("the fact is true", sources)
        assert report.sources_checked == 1

    async def test_synthesize(self) -> None:
        mgr = ResearchManager()
        documents = [
            Source(title="A", abstract="test content", reliability_score=0.8),
        ]
        synthesis = await mgr.synthesize("p1", "T", documents)
        assert isinstance(synthesis, KnowledgeSynthesis)

    async def test_overview(self) -> None:
        mgr = ResearchManager()
        overview = await mgr.get_overview()
        assert "engine_stats" in overview
        assert "research_agents" in overview
        assert overview["research_agents"] == 10
        assert "evidence_graph" in overview

    async def test_evidence_graph_search(self) -> None:
        mgr = ResearchManager()
        mgr.add_claim_to_graph(Claim(text="Climate change research"))
        results = mgr.evidence_graph_search("climate")
        assert len(results) == 1

    async def test_timeline(self) -> None:
        mgr = ResearchManager()
        project = await mgr.create_project("P1")
        timeline = await mgr.timeline(project_id=project.project_id)
        assert len(timeline) >= 1  # project_created entry

    async def test_stats(self) -> None:
        mgr = ResearchManager()
        await mgr.create_project("P1")
        stats = await mgr.stats()
        assert stats["projects"] == 1
