# AAiOS v3.0 — Autonomous Mission & Organization System

**Version:** 3.0
**Status:** Production Ready
**Subsystem:** `services/organization/`

## Overview

The Autonomous Mission & Organization System transforms AAiOS from an
Agent Runtime into an Autonomous AI Organization capable of executing
complex, long-running missions consisting of thousands of coordinated
tasks executed by hundreds of specialized agents under executive
supervision.

This is Layer 0 — a new organizational layer **above** the existing
Supervisor. No existing runtime code was modified; the system is a
pure extension that integrates with the existing event bus, agent
registry, and model router.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   MissionManager (facade)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  Store   │  │  State   │  │   WBS    │  │  Decision    │    │
│  │ (JSON)   │  │ Machine  │  │ Engine   │  │  Engine      │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
│       ↑                ↑              ↑               ↑         │
│       │                │              │               │         │
│  ┌────┴────┐    ┌──────┴──────┐ ┌────┴────┐   ┌──────┴──────┐  │
│  │ Event   │    │ Persistence │ │ Collab  │   │  Resource   │  │
│  │ Bus     │    │ + Recovery  │ │ Engine  │   │  Manager    │  │
│  └─────────┘    │ + Replay    │ │ (vote,  │   │ (agents,    │  │
│                 │ + History   │ │ review) │   │  budget)    │  │
│                 └─────────────┘ └─────────┘   └─────────────┘  │
│                       │                                 │       │
│  ┌────────────┐  ┌────┴──────┐  ┌──────────┐  ┌────────┴────┐  │
│  │ Exporter   │  │ Analytics │  │ Searcher │  │  API + CLI  │  │
│  │ (JSON/CSV) │  │ (portfolio│  │ (TF-IDF) │  │  + Dashboard│  │
│  └────────────┘  └───────────┘  └──────────┘  └─────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                         ↓ (integrates with)
┌─────────────────────────────────────────────────────────────────┐
│              Existing AAiOS v2.x Runtime                         │
│  Event Bus │ Agent Registry │ Model Router │ Supervisor │ ...   │
└─────────────────────────────────────────────────────────────────┘
```

## Organizational Hierarchy

```
Executive Director
    ↓
Chief Strategy Officer
    ↓
Mission Director
    ↓
Mission Planner
    ↓
Mission Supervisor
    ↓
Task Supervisor
    ↓
Task Orchestrator
    ↓
Agent Registry
    ↓
Generic Agents
```

## Components

### 1. Mission (models.py)

The top-level organizational unit with:
- **Identity:** mission_id, title, description, objectives, deliverables
- **Lifecycle:** status (8 states), priority, created_at, started_at, completed_at
- **Budget:** total, spent, reserved, alert threshold, over-budget detection
- **WBS:** list of WBSNode (program → project → epic → feature → story → task → subtask)
- **Risk Register:** list of Risk (probability × impact, mitigation, owner)
- **Milestones:** list of Milestone (target_date, achieved_date, status)
- **Approval Gates:** list of ApprovalGate (pending/approved/rejected)
- **Resources:** ResourceAllocation (agents, providers, concurrency limits)
- **Quality:** QualityMetrics (reflection, QA, user satisfaction, defects)
- **Decisions:** list of Decision (executive decisions with evidence + reasoning)
- **Artifacts:** list of MissionArtifact (produced deliverables)
- **Lessons Learned:** list of strings

### 2. MissionStateMachine (state_machine.py)

8 states with validated transitions:
- `CREATED` → PLANNING, CANCELLED
- `PLANNING` → READY, PLANNING (replan), CANCELLED
- `READY` → EXECUTING, CANCELLED
- `EXECUTING` → PAUSED, COMPLETED, FAILED, PLANNING (replan), CANCELLED
- `PAUSED` → EXECUTING, PLANNING (replan), FAILED, CANCELLED
- `COMPLETED` → (terminal)
- `FAILED` → PLANNING (replan)
- `CANCELLED` → (terminal)

Each transition emits an event on the mission event bus.

### 3. WorkBreakdownEngine (wbs_engine.py)

Decomposes mission objectives into a WBS DAG:
- **Strategies:** `objective_per_project` (default), `single_project`, `flat`
- **Manual nodes:** `add_node()` for custom WBS construction
- **Dependency management:** `add_dependency()`, `validate_dag()` (cycle detection)
- **Topological ordering:** `topological_order()`, `get_execution_layers()` (parallelizable groups)
- **Operations:** `merge_tasks()`, `split_task()`
- **Capability suggestion:** heuristic mapping from task titles to capability namespaces

### 4. DecisionEngine (decision_engine.py)

Evidence-based executive decisions:
- **Evidence collection:** budget utilization, deadline status, quality scores, failure rates, blocked tasks, pending approvals, risk materialization
- **9 decision rules:** pause on over-budget, replan on deadline passed, escalate on approaching deadline, reflect on low quality, switch agent/provider on high failure rate, research on blocked tasks, pause on materialized risks, notify on pending approvals, continue if healthy
- **Recommendations:** sorted by urgency (critical > high > normal > low)
- **Agent/provider selection:** `select_agent_for_task()`, `select_provider_for_task()`

### 5. CollaborationEngine (collaboration.py)

Multi-agent collaboration:
- **Messaging:** direct + broadcast, typed (proposal, bid, vote, review, delegation, conflict)
- **Voting:** yes/no/abstain with quorum + threshold
- **Consensus:** multi-round position convergence
- **Peer review:** agent reviews agent's work (approved / changes_requested / rejected)
- **Delegation:** agent delegates task to another agent
- **Negotiation:** multi-round message exchange
- **Conflict resolution:** vote / mediate / escalate / random
- **Shared memory:** per-mission key-value store for inter-agent knowledge sharing

### 6. ResourceManager (resource_manager.py)

Dynamic resource allocation:
- **Agent assignment:** `assign_agent()`, `release_agent()`, load tracking
- **Provider assignment:** `assign_provider()`, `release_provider()`, load tracking
- **Concurrency limits:** `acquire_task_slot()`, `release_task_slot()` (global + per-mission)
- **Budget management:** `reserve_budget()`, `spend_budget()`, `release_budget_reservation()`
- **Load balancing:** `select_least_loaded_agent()`, `select_least_loaded_provider()`
- **Cleanup:** `release_all_for_mission()` on cancel/complete

### 7. Persistence + Recovery + Replay (persistence.py)

- **MissionPersistence:** atomic JSON snapshots to disk
- **MissionRecovery:** loads all saved missions, transitions EXECUTING → PAUSED
- **MissionReplay:** reconstructs timeline from history entries
- **MissionHistory:** in-memory audit log of all state changes
- **Mission comparison:** `compare_missions()` for A/B analysis

### 8. Analytics + Search + Export (analytics.py)

- **MissionAnalytics:** portfolio metrics (total/active/completed/failed, success rate, budget, duration, top agents/providers, decision type counts), per-mission timeline, WBS dependency graph, success rate trend
- **MissionSearcher:** TF-IDF full-text search over mission titles, descriptions, objectives
- **MissionExporter:** JSON + CSV export with filtering

## API (18 endpoints)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/missions` | List with filtering |
| POST | `/api/v1/missions` | Create mission |
| GET | `/api/v1/missions/{id}` | Get by ID |
| PATCH | `/api/v1/missions/{id}` | Update fields |
| DELETE | `/api/v1/missions/{id}` | Delete |
| POST | `/api/v1/missions/{id}/start` | Start mission |
| POST | `/api/v1/missions/{id}/pause` | Pause mission |
| POST | `/api/v1/missions/{id}/resume` | Resume mission |
| POST | `/api/v1/missions/{id}/cancel` | Cancel mission |
| POST | `/api/v1/missions/{id}/replay` | Replay history |
| GET | `/api/v1/missions/{id}/timeline` | Event timeline |
| GET | `/api/v1/missions/{id}/analytics` | Per-mission analytics |
| GET | `/api/v1/missions/{id}/artifacts` | Artifacts produced |
| GET | `/api/v1/missions/{id}/graph` | WBS dependency graph |
| POST | `/api/v1/missions/{id}/wbs` | Add WBS node |
| GET | `/api/v1/missions/{id}/evaluate` | Decision recommendations |
| GET | `/api/v1/missions/portfolio/metrics` | Portfolio metrics |
| POST | `/api/v1/missions/search` | Search missions |

## CLI (11 commands)

```
aaios mission create   --title "..." --objective "..." --budget 100
aaios mission list     [--status executing]
aaios mission start    <mission_id>
aaios mission stop     <mission_id> [--reason "..."]
aaios mission pause    <mission_id> [--reason "..."]
aaios mission resume   <mission_id>
aaios mission cancel   <mission_id> [--reason "..."]
aaios mission replay   <mission_id>
aaios mission graph    <mission_id>
aaios mission timeline <mission_id>
aaios mission analytics <mission_id>
aaios mission export   [json|csv] [--output file]
```

## Dashboard

- `/missions` — Mission Center (filterable table with status, progress, budget)

## Mission Event Bus

Every state transition publishes an event:
- `mission.created`, `mission.started`, `mission.paused`, `mission.resumed`
- `mission.cancelled`, `mission.completed`, `mission.failed`
- `mission.decision_made`, `mission.replanned`
- `mission.state_changed`

## State Diagram

```
    ┌─────────┐
    │ CREATED │
    └────┬────┘
         │ start()
         ▼
    ┌──────────┐
    │ PLANNING │◄──────────┐
    └────┬─────┘           │
         │                 │ replan()
         ▼                 │
    ┌────────┐             │
    │ READY  │             │
    └────┬───┘             │
         │ start()         │
         ▼                 │
    ┌───────────┐    ┌─────┴──────┐
    │ EXECUTING │───►│   PAUSED   │
    └─────┬─────┘    └─────┬──────┘
          │                 │
    ┌─────┴─────┐     ┌─────┴─────┐
    ▼     ▼     ▼     ▼     ▼     ▼
 COMPLETED FAILED CANCELLED (via any state)
```

## Testing

63 tests across 8 test classes:
- `TestMissionModels` (6) — model creation, serialization, budget/quality/risk
- `TestMissionStateMachine` (6) — valid/invalid transitions, lifecycle, cancel, replan
- `TestMissionStore` (7) — CRUD, filtering, persistence
- `TestWorkBreakdownEngine` (9) — decomposition, DAG validation, topological order, merge/split
- `TestDecisionEngine` (6) — evidence collection, over-budget, deadline, should_start
- `TestCollaborationEngine` (7) — messaging, voting, consensus, review, delegation, shared memory
- `TestResourceManager` (6) — assignment, task slots, budget, load balancing, release all
- `TestMissionManager` (11) — full lifecycle, WBS, evaluate, timeline, graph, search, replay, persistence
- `TestMissionStress` (3) — 100 missions, 100+ WBS nodes, concurrent creation

## File Manifest

```
services/organization/
├── __init__.py           # Public API exports
├── models.py             # Mission + 12 supporting types
├── state_machine.py      # 8 states + transition validation
├── store.py              # MissionStore + Filter + Summary
├── wbs_engine.py         # WorkBreakdownEngine (decompose + DAG)
├── decision_engine.py    # ExecutiveDecisionEngine (9 rules)
├── collaboration.py      # CollaborationEngine (vote/review/delegate)
├── resource_manager.py   # ResourceManager (agents/budget/slots)
├── persistence.py        # Persistence + Recovery + Replay + History
├── analytics.py          # Analytics + Searcher + Exporter
└── manager.py            # MissionManager facade

tests/unit/
└── test_organization.py  # 63 tests

surfaces/api/
└── app.py                # +18 mission endpoints

surfaces/cli/
└── __main__.py           # +11 mission commands

surfaces/web/src/app/
└── missions/page.tsx     # Mission Center dashboard

docs/
└── organization-system.md # This document
```
