"""Multi-Agent Collaboration — negotiation, voting, peer review, delegation.

Enables agents to collaborate on mission tasks:
  - Agent negotiation: agents propose/bid on tasks
  - Consensus + voting: multiple agents vote on decisions
  - Peer review: agents review each other's work
  - Conflict resolution: mediator resolves disagreements
  - Delegation: agents delegate subtasks to other agents
  - Inter-agent messaging: typed message passing
  - Shared memory: agents contribute to a shared mission memory
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "AgentMessage",
    "MessageType",
    "CollaborationEngine",
    "ConflictResolution",
    "ConsensusResult",
    "DelegationRequest",
    "DelegationResult",
    "NegotiationResult",
    "PeerReview",
    "ReviewVerdict",
    "Vote",
    "VotingResult",
]


class MessageType(StrEnum):
    """Inter-agent message types."""

    PROPOSAL = "proposal"
    BID = "bid"
    VOTE = "vote"
    REVIEW_REQUEST = "review_request"
    REVIEW_RESPONSE = "review_response"
    DELEGATION_REQUEST = "delegation_request"
    DELEGATION_RESPONSE = "delegation_response"
    CONFLICT_NOTIFICATION = "conflict_notification"
    CONFLICT_RESOLUTION = "conflict_resolution"
    BROADCAST = "broadcast"
    DIRECT = "direct"
    SHARED_MEMORY_UPDATE = "shared_memory_update"


class ReviewVerdict(StrEnum):
    """Peer review verdicts."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    NEEDS_DISCUSSION = "needs_discussion"


@dataclass
class AgentMessage:
    """A message between agents."""

    message_id: str = field(default_factory=lambda: uuid4().hex[:12])
    message_type: str = MessageType.DIRECT.value
    from_agent_id: str = ""
    to_agent_id: str | None = None  # None = broadcast
    mission_id: str | None = None
    wbs_node_id: str | None = None
    content: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    in_reply_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "mission_id": self.mission_id,
            "wbs_node_id": self.wbs_node_id,
            "content": self.content,
            "payload": dict(self.payload),
            "timestamp": self.timestamp.isoformat(),
            "in_reply_to": self.in_reply_to,
        }


@dataclass
class Vote:
    """A single vote from an agent."""

    agent_id: str
    vote: str  # "yes", "no", "abstain"
    reasoning: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class VotingResult:
    """Result of a voting round."""

    proposal_id: str
    question: str
    votes: list[Vote] = field(default_factory=list)
    quorum: int = 2
    threshold: float = 0.5  # fraction of yes votes needed to pass

    @property
    def yes_count(self) -> int:
        return sum(1 for v in self.votes if v.vote == "yes")

    @property
    def no_count(self) -> int:
        return sum(1 for v in self.votes if v.vote == "no")

    @property
    def abstain_count(self) -> int:
        return sum(1 for v in self.votes if v.vote == "abstain")

    @property
    def total_votes(self) -> int:
        return len(self.votes)

    @property
    def has_quorum(self) -> bool:
        return self.total_votes >= self.quorum

    @property
    def passed(self) -> bool:
        if not self.has_quorum:
            return False
        return self.yes_count / max(1, self.yes_count + self.no_count) >= self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "question": self.question,
            "yes_count": self.yes_count,
            "no_count": self.no_count,
            "abstain_count": self.abstain_count,
            "total_votes": self.total_votes,
            "has_quorum": self.has_quorum,
            "passed": self.passed,
            "votes": [
                {
                    "agent_id": v.agent_id,
                    "vote": v.vote,
                    "reasoning": v.reasoning,
                    "timestamp": v.timestamp.isoformat(),
                }
                for v in self.votes
            ],
        }


@dataclass
class ConsensusResult:
    """Result of a consensus round."""

    topic: str
    participants: list[str] = field(default_factory=list)
    positions: dict[str, str] = field(default_factory=dict)  # agent_id → position
    consensus_reached: bool = False
    consensus_position: str | None = None
    rounds: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "participants": list(self.participants),
            "positions": dict(self.positions),
            "consensus_reached": self.consensus_reached,
            "consensus_position": self.consensus_position,
            "rounds": self.rounds,
        }


@dataclass
class PeerReview:
    """A peer review of an agent's work by another agent."""

    review_id: str = field(default_factory=lambda: uuid4().hex[:12])
    reviewer_agent_id: str = ""
    reviewed_agent_id: str = ""
    wbs_node_id: str | None = None
    mission_id: str | None = None
    verdict: str = ReviewVerdict.CHANGES_REQUESTED.value
    quality_score: float = 0.0
    comments: str = ""
    suggested_changes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "reviewer_agent_id": self.reviewer_agent_id,
            "reviewed_agent_id": self.reviewed_agent_id,
            "wbs_node_id": self.wbs_node_id,
            "mission_id": self.mission_id,
            "verdict": self.verdict,
            "quality_score": round(self.quality_score, 4),
            "comments": self.comments,
            "suggested_changes": list(self.suggested_changes),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DelegationRequest:
    """A request from one agent to delegate a task to another."""

    delegation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    from_agent_id: str = ""
    to_agent_id: str = ""
    wbs_node_id: str | None = None
    mission_id: str | None = None
    task_description: str = ""
    capabilities_required: list[str] = field(default_factory=list)
    deadline: datetime | None = None
    justification: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "wbs_node_id": self.wbs_node_id,
            "mission_id": self.mission_id,
            "task_description": self.task_description,
            "capabilities_required": list(self.capabilities_required),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "justification": self.justification,
        }


@dataclass
class DelegationResult:
    """Result of a delegation request."""

    delegation_id: str
    accepted: bool
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "accepted": self.accepted,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class NegotiationResult:
    """Result of a negotiation between agents."""

    negotiation_id: str = field(default_factory=lambda: uuid4().hex[:12])
    topic: str = ""
    participants: list[str] = field(default_factory=list)
    rounds: int = 0
    agreement_reached: bool = False
    final_position: str | None = None
    messages: list[AgentMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "negotiation_id": self.negotiation_id,
            "topic": self.topic,
            "participants": list(self.participants),
            "rounds": self.rounds,
            "agreement_reached": self.agreement_reached,
            "final_position": self.final_position,
            "messages": [m.to_dict() for m in self.messages],
        }


@dataclass
class ConflictResolution:
    """Result of conflict resolution between agents."""

    conflict_id: str = field(default_factory=lambda: uuid4().hex[:12])
    mission_id: str | None = None
    conflicting_agents: list[str] = field(default_factory=list)
    issue: str = ""
    resolution_strategy: str = ""  # vote, mediate, escalate, random
    resolved_by: str = ""
    resolution: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "mission_id": self.mission_id,
            "conflicting_agents": list(self.conflicting_agents),
            "issue": self.issue,
            "resolution_strategy": self.resolution_strategy,
            "resolved_by": self.resolved_by,
            "resolution": self.resolution,
            "timestamp": self.timestamp.isoformat(),
        }


class CollaborationEngine:
    """Manages multi-agent collaboration for missions.

    Provides:
      - Inter-agent messaging (direct + broadcast)
      - Voting (yes/no/abstain with quorum + threshold)
      - Consensus (multi-round position convergence)
      - Peer review (agents reviewing each other's work)
      - Delegation (agents handing off tasks)
      - Negotiation (multi-round message exchange)
      - Conflict resolution (vote/mediate/escalate)
      - Shared memory (agents contributing to a shared knowledge base)
    """

    def __init__(self) -> None:
        self._messages: list[AgentMessage] = []
        self._inbox: dict[str, list[AgentMessage]] = defaultdict(list)  # agent_id → messages
        self._broadcast_inbox: list[AgentMessage] = []
        self._shared_memory: dict[str, dict[str, Any]] = defaultdict(
            dict
        )  # mission_id → key → value
        self._lock = asyncio.Lock()

    async def send_message(self, message: AgentMessage) -> AgentMessage:
        """Send a message from one agent to another (or broadcast)."""
        async with self._lock:
            self._messages.append(message)
            if message.to_agent_id is None:
                # Broadcast — goes to all agents' inboxes
                self._broadcast_inbox.append(message)
            else:
                self._inbox[message.to_agent_id].append(message)
        _log.debug(
            "Agent message: %s → %s (%s)",
            message.from_agent_id,
            message.to_agent_id or "all",
            message.message_type,
        )
        return message

    async def get_messages(
        self,
        agent_id: str,
        *,
        include_broadcast: bool = True,
    ) -> list[AgentMessage]:
        """Get all messages for an agent."""
        async with self._lock:
            messages = list(self._inbox.get(agent_id, []))
            if include_broadcast:
                messages.extend(self._broadcast_inbox)
            return messages

    async def clear_inbox(self, agent_id: str) -> int:
        """Clear an agent's inbox. Returns count cleared."""
        async with self._lock:
            count = len(self._inbox.get(agent_id, []))
            self._inbox[agent_id] = []
            return count

    async def conduct_vote(
        self,
        question: str,
        participants: list[str],
        *,
        quorum: int = 2,
        threshold: float = 0.5,
        votes: list[Vote] | None = None,
    ) -> VotingResult:
        """Conduct a voting round.

        In a real system, this would asynchronously collect votes from
        agents. For testing + programmatic use, votes can be provided
        directly.
        """
        proposal_id = uuid4().hex[:12]
        result = VotingResult(
            proposal_id=proposal_id,
            question=question,
            quorum=quorum,
            threshold=threshold,
        )
        if votes:
            result.votes = votes
        else:
            # Simulate: each participant votes yes (in production, ask agents)
            result.votes = [
                Vote(agent_id=aid, vote="yes", reasoning="auto-approve") for aid in participants
            ]
        return result

    async def seek_consensus(
        self,
        topic: str,
        participants: list[str],
        positions: dict[str, str] | None = None,
        *,
        max_rounds: int = 3,
    ) -> ConsensusResult:
        """Seek consensus among agents on a topic.

        In a real system, this would run multiple rounds of discussion.
        For testing, if all positions agree, consensus is reached immediately.
        """
        result = ConsensusResult(
            topic=topic,
            participants=list(participants),
            positions=positions or {},
        )
        if positions:
            unique_positions = set(positions.values())
            if len(unique_positions) <= 1:
                result.consensus_reached = True
                result.consensus_position = next(iter(unique_positions), None)
                result.rounds = 1
            else:
                # Simulate convergence: after max_rounds, take majority position
                from collections import Counter

                position_counts = Counter(positions.values())
                result.consensus_position = position_counts.most_common(1)[0][0]
                result.consensus_reached = len(position_counts) == 1
                result.rounds = max_rounds
        return result

    async def request_peer_review(
        self,
        reviewer_agent_id: str,
        reviewed_agent_id: str,
        *,
        wbs_node_id: str | None = None,
        mission_id: str | None = None,
        quality_score: float = 0.0,
        comments: str = "",
        verdict: str = ReviewVerdict.APPROVED.value,
        suggested_changes: list[str] | None = None,
    ) -> PeerReview:
        """Conduct a peer review.

        In a real system, this would send a review request and wait for
        the reviewer to respond. For testing, the review is provided directly.
        """
        review = PeerReview(
            reviewer_agent_id=reviewer_agent_id,
            reviewed_agent_id=reviewed_agent_id,
            wbs_node_id=wbs_node_id,
            mission_id=mission_id,
            verdict=verdict,
            quality_score=quality_score,
            comments=comments,
            suggested_changes=suggested_changes or [],
        )
        _log.info(
            "Peer review: %s reviewed %s (verdict=%s, score=%.2f)",
            reviewer_agent_id,
            reviewed_agent_id,
            verdict,
            quality_score,
        )
        return review

    async def delegate_task(
        self,
        request: DelegationRequest,
        *,
        accepted: bool = True,
        reason: str = "",
    ) -> DelegationResult:
        """Delegate a task from one agent to another.

        In a real system, this would send the request and wait for
        acceptance. For testing, the result is provided directly.
        """
        result = DelegationResult(
            delegation_id=request.delegation_id,
            accepted=accepted,
            reason=reason or ("Delegation accepted" if accepted else "Delegation declined"),
        )
        _log.info(
            "Delegation: %s → %s (accepted=%s)",
            request.from_agent_id,
            request.to_agent_id,
            accepted,
        )
        return result

    async def negotiate(
        self,
        topic: str,
        participants: list[str],
        *,
        messages: list[AgentMessage] | None = None,
        max_rounds: int = 5,
    ) -> NegotiationResult:
        """Conduct a negotiation between agents.

        In a real system, this would run multiple rounds of message
        exchange. For testing, messages can be provided directly.
        """
        result = NegotiationResult(
            topic=topic,
            participants=list(participants),
            messages=messages or [],
            rounds=max_rounds if messages else 0,
        )
        if messages:
            # Simple heuristic: if last message contains "agree", agreement reached
            last_content = messages[-1].content.lower() if messages else ""
            result.agreement_reached = "agree" in last_content
            result.final_position = messages[-1].content if result.agreement_reached else None
        return result

    async def resolve_conflict(
        self,
        conflicting_agents: list[str],
        issue: str,
        *,
        strategy: str = "vote",
        mission_id: str | None = None,
        votes: list[Vote] | None = None,
    ) -> ConflictResolution:
        """Resolve a conflict between agents.

        Strategies:
          - vote: majority vote among conflicting agents
          - mediate: a third party (mission supervisor) decides
          - escalate: escalate to mission director
          - random: random selection (for testing)
        """
        resolution = ConflictResolution(
            mission_id=mission_id,
            conflicting_agents=list(conflicting_agents),
            issue=issue,
            resolution_strategy=strategy,
        )
        if strategy == "vote" and votes:
            voting = await self.conduct_vote(
                question=issue,
                participants=conflicting_agents,
                votes=votes,
            )
            resolution.resolution = f"Voted: yes={voting.yes_count}, no={voting.no_count}"
            resolution.resolved_by = "vote"
        elif strategy == "mediate":
            resolution.resolution = "Mediated by mission supervisor"
            resolution.resolved_by = "mission_supervisor"
        elif strategy == "escalate":
            resolution.resolution = "Escalated to mission director"
            resolution.resolved_by = "mission_director"
        else:
            import secrets

            winner = secrets.choice(conflicting_agents) if conflicting_agents else "none"  # nosec S311 — non-cryptographic use
            resolution.resolution = f"Random selection: {winner}"
            resolution.resolved_by = "random"
        return resolution

    async def update_shared_memory(
        self,
        mission_id: str,
        key: str,
        value: Any,
        *,
        agent_id: str = "",
    ) -> None:
        """Update a key in the mission's shared memory."""
        async with self._lock:
            self._shared_memory[mission_id][key] = value
        _log.debug(
            "Shared memory update: mission=%s key=%s by=%s",
            mission_id,
            key,
            agent_id,
        )

    async def get_shared_memory(
        self,
        mission_id: str,
        key: str | None = None,
    ) -> Any:
        """Get a value from shared memory, or the entire dict if key is None."""
        async with self._lock:
            if key is None:
                return dict(self._shared_memory.get(mission_id, {}))
            return self._shared_memory.get(mission_id, {}).get(key)

    async def get_all_messages(
        self,
        mission_id: str | None = None,
    ) -> list[AgentMessage]:
        """Get all messages, optionally filtered by mission."""
        async with self._lock:
            if mission_id is None:
                return list(self._messages)
            return [m for m in self._messages if m.mission_id == mission_id]
