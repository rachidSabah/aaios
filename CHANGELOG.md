# Changelog

All notable changes to AAiOS are documented in this file.

## [4.1.0] — 2026-07-16

### Production Completion

#### Execution Platform (v4.0 + v4.1)
- **16 execution domains**: filesystem, terminal, git, docker, kubernetes, SSH, database, REST API, browser, desktop, cloud, CI/CD, document, spreadsheet, email, calendar, communication
- **Zero stubs remaining**: every handler either executes real work or degrades gracefully with clear install instructions
- **Persistent audit system**: SQLite-backed with SHA-256 hash chain validation, JSONL export, retention policies
- **Production approval engine**: blocking approvals, timeout, escalation, multi-user, role-based (4-role hierarchy)
- **Execution dashboard**: live jobs, approval queue, KPI cards, filters, responsive layout

#### Enterprise Intelligence Layer (v3.1)
- **12 health dimensions**: operational, mission, agent efficiency, provider efficiency, workflow quality, execution success, risk level, reliability, cost efficiency, learning velocity, innovation
- **10 forecast types**: mission failure, workflow bottleneck, provider outage, agent degradation, memory saturation, queue congestion, budget overrun, deadline risk, resource exhaustion, capacity limit
- **9 optimization recommendation types**: routing, provider selection, agent assignment, workflow, prompt, scheduling, concurrency, retry strategy, caching, memory utilization
- **Digital twin**: 12-node system graph with health scores
- **7 report types**: daily executive, weekly operations, monthly performance, reliability, optimization, risk, mission

#### Autonomous Mission System (v3.0)
- **8-state lifecycle**: created → planning → ready → executing ↔ paused → completed/failed/cancelled
- **Work Breakdown Engine**: 3 decomposition strategies, DAG validation, topological ordering, merge/split
- **Executive Decision Engine**: 9 evidence-based rules (pause, cancel, replan, reflect, switch, research, notify, continue)
- **Multi-agent collaboration**: messaging, voting, consensus, peer review, delegation, negotiation, conflict resolution
- **Resource manager**: agent/provider allocation, load balancing, concurrency limits, budget tracking

#### Experience & Learning Engine (v2.1)
- **Immutable experience records**: 30+ fields capturing full task lifecycle
- **TF-IDF semantic search**: 6 search types (similar successes, similar failures, best agent, fastest provider, cheapest provider, highest quality)
- **Pattern discovery**: success patterns, failure patterns, repeated fixes
- **Reliability scoring**: per-agent, per-provider, per-capability with trend detection
- **Replay**: dry_run, re_execute, compare modes

#### Core Platform (v1.0–v2.0)
- **5-layer architecture**: Kernel → Services → Agents → Supervision → Surfaces
- **13 LLM providers**: OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA, Ollama, LM Studio, Azure OpenAI, Mistral, Groq, Custom
- **Real MCP**: subprocess + JSON-RPC over stdio
- **FastAPI**: 96 REST endpoints + WebSocket
- **Typer CLI**: 40+ commands across 7 command groups
- **Next.js 16 dashboard**: 10 pages (overview, intelligence, missions, execution, workflows, monitoring, analytics, experience, learning)
- **Windows native**: Services, Job Objects, AppContainer, WDAC, Task Scheduler
- **Distributed runtime**: multi-node orchestration with heartbeats, scatter/gather

### Quality
- 907 automated tests (unit + integration + e2e + performance + security)
- ruff: 0 issues
- mypy --strict: 0 issues
- bandit: 0 issues
- 907/907 tests passing

### Breaking Changes
None. v4.1 is a strict superset of all previous versions.

## [1.0.0] — 2025-07-13

Initial release. See git history for details.
