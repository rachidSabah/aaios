"""Phase 4 — Evidence Graph.

A searchable graph of claims, facts, sources, documents, reports, and
research sessions. Edges encode support, contradiction, dependency,
reference, and citation relationships. Every edge carries an evidence
strength weight.

The graph is in-memory and indexed for fast lookup. It is read-only
from the outside — mutation happens via the public ``add_*`` methods
which record provenance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from core.logging import get_logger
from services.research.models import (
    Claim,
    ClaimRelation,
    ClaimRelationType,
    EvidenceNode,
    EvidenceRelation,
    EvidenceRelationType,
    Fact,
    Source,
)

_log = get_logger(__name__)

__all__ = ["EvidenceGraph"]


class EvidenceGraph:
    """Phase 4 — Evidence Graph.

    Nodes: claim, fact, source, document, report, session.
    Edges: support, contradiction, dependency, reference, citation.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, EvidenceNode] = {}
        self._edges: dict[str, EvidenceRelation] = {}
        self._claims: dict[str, Claim] = {}
        self._facts: dict[str, Fact] = {}
        self._sources: dict[str, Source] = {}
        self._documents: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        # Adjacency: source_node_id -> list of edge_ids
        self._outgoing: dict[str, list[str]] = defaultdict(list)
        self._incoming: dict[str, list[str]] = defaultdict(list)

    # --- Add nodes ------------------------------------------------------

    def add_claim(self, claim: Claim) -> EvidenceNode:
        """Register a claim as a graph node."""
        self._claims[claim.claim_id] = claim
        node = EvidenceNode(
            kind="claim",
            ref_id=claim.claim_id,
            label=claim.text[:80] if claim.text else f"claim-{claim.claim_id}",
            weight=claim.confidence,
            metadata={"claim_type": claim.claim_type, "verified": claim.verified},
        )
        self._nodes[node.node_id] = node
        return node

    def add_fact(self, fact: Fact) -> EvidenceNode:
        """Register a verified fact as a graph node."""
        self._facts[fact.fact_id] = fact
        node = EvidenceNode(
            kind="fact",
            ref_id=fact.fact_id,
            label=fact.text[:80] if fact.text else f"fact-{fact.fact_id}",
            weight=fact.confidence,
            metadata={"verified": fact.verified, "status": fact.verification_status},
        )
        self._nodes[node.node_id] = node
        return node

    def add_source(self, source: Source) -> EvidenceNode:
        """Register a source as a graph node."""
        self._sources[source.source_id] = source
        node = EvidenceNode(
            kind="source",
            ref_id=source.source_id,
            label=source.title[:80] if source.title else f"source-{source.source_id}",
            weight=source.reliability_score,
            metadata={
                "reliability": source.reliability,
                "source_type": source.source_type,
                "citation_count": source.citation_count,
            },
        )
        self._nodes[node.node_id] = node
        return node

    def add_document(
        self, doc_id: str, title: str, metadata: dict[str, Any] | None = None
    ) -> EvidenceNode:
        """Register a document node."""
        self._documents[doc_id] = {"title": title, "metadata": metadata or {}}
        node = EvidenceNode(
            kind="document",
            ref_id=doc_id,
            label=title[:80] if title else f"document-{doc_id}",
            weight=1.0,
            metadata=metadata or {},
        )
        self._nodes[node.node_id] = node
        return node

    def add_report(
        self, report_id: str, title: str, metadata: dict[str, Any] | None = None
    ) -> EvidenceNode:
        """Register a report node."""
        self._reports[report_id] = {"title": title, "metadata": metadata or {}}
        node = EvidenceNode(
            kind="report",
            ref_id=report_id,
            label=title[:80] if title else f"report-{report_id}",
            weight=1.0,
            metadata=metadata or {},
        )
        self._nodes[node.node_id] = node
        return node

    def add_session(
        self, session_id: str, title: str, metadata: dict[str, Any] | None = None
    ) -> EvidenceNode:
        """Register a research session node."""
        self._sessions[session_id] = {"title": title, "metadata": metadata or {}}
        node = EvidenceNode(
            kind="session",
            ref_id=session_id,
            label=title[:80] if title else f"session-{session_id}",
            weight=1.0,
            metadata=metadata or {},
        )
        self._nodes[node.node_id] = node
        return node

    # --- Add edges ------------------------------------------------------

    def add_relation(
        self,
        source_node_id: str,
        target_node_id: str,
        relation_type: EvidenceRelationType | str,
        *,
        weight: float = 0.5,
        evidence: list[str] | None = None,
        explanation: str = "",
    ) -> EvidenceRelation | None:
        """Add a typed edge between two nodes."""
        rt = (
            relation_type.value
            if isinstance(relation_type, EvidenceRelationType)
            else relation_type
        )
        if source_node_id not in self._nodes or target_node_id not in self._nodes:
            return None
        edge = EvidenceRelation(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=rt,
            weight=weight,
            evidence=evidence or [],
            explanation=explanation,
        )
        self._edges[edge.edge_id] = edge
        self._outgoing[source_node_id].append(edge.edge_id)
        self._incoming[target_node_id].append(edge.edge_id)
        return edge

    def add_claim_relation(self, relation: ClaimRelation) -> EvidenceRelation | None:
        """Add a claim-to-claim relation. Both claims must be registered first."""
        source_node = self._find_node_for_ref("claim", relation.source_claim_id)
        target_node = self._find_node_for_ref("claim", relation.target_claim_id)
        if not source_node or not target_node:
            return None
        # Map ClaimRelationType to EvidenceRelationType
        type_map = {
            ClaimRelationType.SUPPORTS.value: EvidenceRelationType.SUPPORT.value,
            ClaimRelationType.CONTRADICTS.value: EvidenceRelationType.CONTRADICTION.value,
            ClaimRelationType.DEPENDS_ON.value: EvidenceRelationType.DEPENDENCY.value,
            ClaimRelationType.REFERENCES.value: EvidenceRelationType.REFERENCE.value,
            ClaimRelationType.CITES.value: EvidenceRelationType.CITATION.value,
            ClaimRelationType.DERIVED_FROM.value: EvidenceRelationType.DEPENDENCY.value,
        }
        return self.add_relation(
            source_node.node_id,
            target_node.node_id,
            type_map.get(relation.relation_type, EvidenceRelationType.REFERENCE.value),
            weight=relation.weight,
            explanation=relation.explanation,
        )

    def _find_node_for_ref(self, kind: str, ref_id: str) -> EvidenceNode | None:
        for node in self._nodes.values():
            if node.kind == kind and node.ref_id == ref_id:
                return node
        return None

    # --- Query ----------------------------------------------------------

    def get_node(self, node_id: str) -> EvidenceNode | None:
        return self._nodes.get(node_id)

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def get_fact(self, fact_id: str) -> Fact | None:
        return self._facts.get(fact_id)

    def get_source(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def list_nodes(
        self,
        *,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceNode]:
        out = list(self._nodes.values())
        if kind:
            out = [n for n in out if n.kind == kind]
        return out[:limit]

    def list_edges(
        self,
        *,
        relation_type: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceRelation]:
        out = list(self._edges.values())
        if relation_type:
            out = [e for e in out if e.relation_type == relation_type]
        return out[:limit]

    def neighbors(
        self,
        node_id: str,
        *,
        relation_type: str | None = None,
        direction: str = "both",
    ) -> list[EvidenceNode]:
        """Return neighboring nodes."""
        if node_id not in self._nodes:
            return []
        edge_ids: list[str] = []
        if direction in ("out", "both"):
            edge_ids.extend(self._outgoing.get(node_id, []))
        if direction in ("in", "both"):
            edge_ids.extend(self._incoming.get(node_id, []))
        neighbor_ids: set[str] = set()
        for eid in edge_ids:
            edge = self._edges.get(eid)
            if not edge:
                continue
            if relation_type and edge.relation_type != relation_type:
                continue
            if edge.source_node_id != node_id:
                neighbor_ids.add(edge.source_node_id)
            if edge.target_node_id != node_id:
                neighbor_ids.add(edge.target_node_id)
        return [self._nodes[nid] for nid in neighbor_ids if nid in self._nodes]

    def supporting_evidence(self, claim_id: str) -> list[EvidenceRelation]:
        """All edges that support the given claim."""
        node = self._find_node_for_ref("claim", claim_id)
        if not node:
            return []
        return [
            self._edges[eid]
            for eid in self._incoming.get(node.node_id, [])
            if self._edges[eid].relation_type == EvidenceRelationType.SUPPORT.value
        ]

    def contradicting_evidence(self, claim_id: str) -> list[EvidenceRelation]:
        """All edges that contradict the given claim."""
        node = self._find_node_for_ref("claim", claim_id)
        if not node:
            return []
        return [
            self._edges[eid]
            for eid in self._incoming.get(node.node_id, [])
            if self._edges[eid].relation_type == EvidenceRelationType.CONTRADICTION.value
        ]

    def search(self, query: str, *, kinds: list[str] | None = None) -> list[EvidenceNode]:
        """Substring search across node labels."""
        q = query.lower()
        out: list[EvidenceNode] = []
        for node in self._nodes.values():
            if kinds and node.kind not in kinds:
                continue
            if q in node.label.lower():
                out.append(node)
        return out

    def evidence_strength(self, node_id: str) -> float:
        """Aggregate evidence strength for a node.

        Computed as the weighted sum of incoming support edges minus
        weighted contradiction edges, clamped to [0, 1].
        """
        if node_id not in self._nodes:
            return 0.0
        support = 0.0
        contradiction = 0.0
        for eid in self._incoming.get(node_id, []):
            edge = self._edges.get(eid)
            if not edge:
                continue
            if edge.relation_type == EvidenceRelationType.SUPPORT.value:
                support += edge.weight
            elif edge.relation_type == EvidenceRelationType.CONTRADICTION.value:
                contradiction += edge.weight
        # Weighted by source node weights
        for eid in self._incoming.get(node_id, []):
            edge = self._edges.get(eid)
            if not edge:
                continue
            src = self._nodes.get(edge.source_node_id)
            if not src:
                continue
            if edge.relation_type == EvidenceRelationType.SUPPORT.value:
                support *= src.weight
            elif edge.relation_type == EvidenceRelationType.CONTRADICTION.value:
                contradiction *= src.weight
        strength = support - contradiction
        return round(max(0.0, min(1.0, strength)), 4)

    # --- Stats ----------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        by_kind: dict[str, int] = defaultdict(int)
        for n in self._nodes.values():
            by_kind[n.kind] += 1
        by_relation: dict[str, int] = defaultdict(int)
        for e in self._edges.values():
            by_relation[e.relation_type] += 1
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "claims": len(self._claims),
            "facts": len(self._facts),
            "sources": len(self._sources),
            "documents": len(self._documents),
            "reports": len(self._reports),
            "sessions": len(self._sessions),
            "nodes_by_kind": dict(by_kind),
            "edges_by_type": dict(by_relation),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "stats": self.stats(),
        }
