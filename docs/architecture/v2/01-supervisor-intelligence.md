# AAiOS v2.0 — Supervisor Intelligence Architecture

> **Status:** Draft — v2.0 expansion phase
> **Depends on:** v1.0 architecture (all 10 docs in `docs/architecture/`)
> **Scope:** Supervisor intelligence, adaptive routing, persistent planning,
> multi-agent collaboration, autonomous jobs, self-improving policies

---

## 1. What v2.0 adds

v1.0 established the foundation: GenericAgent runtime, capability-based
selection, task orchestrator, model router, memory, security. The supervisor
works but is "dumb" — it plans, dispatches, reflects, and commits without
learning from its mistakes.

v2.0 makes the supervisor **intelligent**:

| v1.0 (dumb) | v2.0 (intelligent) |
|-------------|-------------------|
| Static capability scoring | Adaptive routing that learns from execution history |
| Plans lost on reboot | Persistent planning across reboots |
| Supervisor → agent (one-way) | Multi-agent collaboration (agents delegate to each other) |
| Tasks end when the process ends | Long-running autonomous jobs (hours/days) |
| Same policy forever | Self-improving policies that adapt based on outcomes |
| Manual retry/correction | Automatic strategy adjustment based on failure patterns |

## 2. New components

### 2.1 ExecutionHistory
Tracks every step execution: which agent, which capability, which model,
the result, the cost, the latency, the reflection verdict. This is the
training data for the adaptive router and self-improving policy.

```
ExecutionHistory
├─ step_id: UUID
├─ task_id: UUID
├─ agent_id: str
├─ capability: str
├─ model: str
├─ provider: str
├─ status: success | failure | cancelled
├─ cost_usd: float
├─ latency_ms: float
├─ reflection_verdict: accept | reject | needs_correction
├─ qa_verdict: pass | fail
├─ correction_attempts: int
├─ timestamp: datetime
└─ metadata: dict
```

### 2.2 AdaptiveRouter
Replaces the static CapabilitySelector. Instead of fixed weights
(40/20/20/15/5), the router learns optimal weights from execution history.

**Learning loop:**
1. After every step, record the outcome in ExecutionHistory
2. Every N executions (default 50), recompute agent scores based on:
   - Recent success rate (last 100 executions for this capability)
   - Recent cost (weighted average, decayed)
   - Recent latency (p95, decayed)
   - Correction rate (how often reflection rejected)
3. Adjust routing weights automatically
4. Log the weight change for auditability

### 2.3 PersistentPlanner
Plans survive reboots. The planner writes every plan to the State Manager
(event-sourced). On reboot:
1. Load all incomplete plans from the event log
2. For each plan, find the latest checkpoint
3. Restore agent states from the checkpoint
4. Resume execution from the next pending step

This requires the Orchestrator to persist plans to the event store (not
just in-memory). The v1.0 Orchestrator already has checkpointing — v2.0
adds plan persistence.

### 2.4 MultiAgentCollaboration
Agents can delegate to each other. Currently, only the supervisor dispatches.
In v2.0:

- An agent can request another agent's help via `context.delegate(capability, task)`
- The supervisor mediates the delegation (no direct agent-to-agent calls)
- Delegation is tracked as a sub-task with its own event stream
- The delegating agent waits for the sub-task result

Example: Claude Code (CodingAgent) needs to search the web → delegates to
ResearchAgent → ResearchAgent returns results → Claude Code continues.

### 2.5 AutonomousJobScheduler
Long-running jobs that persist across reboots:
- Cron schedules (backed by Task Scheduler on Windows, APScheduler on Linux)
- Interval schedules (every N minutes)
- Event-triggered (run when a specific event occurs)
- Deadlock-free: jobs can be paused, resumed, cancelled

Jobs are stored in the event store and restored on boot. A job is just a
Plan with a schedule attached.

### 2.6 SelfImprovingPolicy
The supervisor's policy (when to retry, when to replan, when to ask the
user) adapts based on execution history:

- If a specific capability fails >30% of the time → suggest adding a new agent
- If a specific agent's correction rate is >50% → degrade its score
- If a specific model is consistently slower for the same quality → switch
- If reflection rejects >20% of outputs for a capability → suggest prompt changes
- If QA fails >10% of the time → suggest success criterion refinement

The policy doesn't modify code — it adjusts routing weights, retry counts,
and escalation thresholds. Changes are logged for auditability.

## 3. Architecture changes

### 3.1 Supervisor loop upgrade

```
v1.0:  goal → plan → dispatch → reflect → correct → QA → commit
v2.0:  goal → plan → dispatch → reflect → correct → QA → commit → LEARN
                                                              ↓
                                              ExecutionHistory.record()
                                                              ↓
                                              AdaptiveRouter.update_weights()
                                                              ↓
                                              SelfImprovingPolicy.adjust()
```

### 3.2 Delegation flow

```
Agent A executes step
  → A needs help with capability X
  → A calls context.delegate(X, subtask)
  → Supervisor receives delegation request
  → Supervisor selects Agent B for capability X
  → Agent B executes subtask
  → Result returned to Agent A
  → Agent A continues
```

### 3.3 Boot sequence upgrade

```
v1.0 boot: kernel → security → router → memory → registry → orchestrator → API
v2.0 boot: kernel → security → router → memory → registry → orchestrator
           → ExecutionHistory (load from event store)
           → AdaptiveRouter (recompute weights from history)
           → PersistentPlanner (restore incomplete plans)
           → AutonomousJobScheduler (restore scheduled jobs)
           → SelfImprovingPolicy (load current policy)
           → Supervisor (start with intelligent routing)
           → API
```

## 4. Backward compatibility

- v1.0 agents work unchanged (GenericAgent interface is the same)
- v1.0 plans work unchanged (Plan/Step contracts are the same)
- v1.0 tests pass (new components are additive, not replacing)
- The CapabilitySelector still exists — AdaptiveRouter extends it
- The DefaultSupervisor still exists — v2.0 adds IntelligentSupervisor

## 5. File layout

```
supervisor/
├─ v2/
│  ├─ __init__.py
│  ├─ execution_history.py      # ExecutionHistory — tracks every step
│  ├─ adaptive_router.py        # AdaptiveRouter — learns from history
│  ├─ persistent_planner.py     # PersistentPlanner — survives reboots
│  ├─ delegation.py             # MultiAgentCollaboration — agent-to-agent
│  ├─ autonomous_jobs.py        # AutonomousJobScheduler — long-running
│  ├─ self_improving.py         # SelfImprovingPolicy — adapts policy
│  └─ intelligent_supervisor.py # IntelligentSupervisor — v2.0 main loop
├─ agent.py                     # v1.0 DefaultSupervisor (unchanged)
├─ capability_selector.py       # v1.0 CapabilitySelector (unchanged)
├─ planner.py                   # v1.0 LlmPlanner (unchanged)
├─ reflection.py                # v1.0 DefaultReflectionAgent (unchanged)
├─ correction.py                # v1.0 DefaultSelfCorrectionAgent (unchanged)
└─ qa.py                        # v1.0 DefaultQAAgent (unchanged)
```
