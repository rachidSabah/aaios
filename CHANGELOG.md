# Changelog

All notable changes to AAiOS are documented in this file.

## [5.3.2] — 2026-07-16

### Enterprise Installation, Bootstrap & Configuration (Part 1)

This release adds a complete self-installing, self-configuring,
self-validating installer. A completely clean Windows 11 (or Linux/WSL2)
machine can become fully operational with a single command.

#### Phase 1 — Environment Discovery
- EnvironmentDetector: detects OS, hardware, network, security, and tools
- CompatibilityReport: assesses against minimum requirements
- InstallationPlan: builds a step-by-step plan from environment + mode
- RiskReport: identifies risks before installation

#### Phase 2 — Dependency Discovery
- DependencyRegistry: 30+ known dependencies (Python, Git, Node, Docker,
  PostgreSQL, Qdrant, Redis, Ollama, LM Studio, Claude Code, OpenCode,
  Hermes, Codex CLI, Gemini CLI, OpenHands, Cline, Roo Code, winget,
  Chocolatey, Scoop, GitHub CLI, Playwright, VC++ Runtime, .NET, WSL, Hyper-V)
- DependencyChecker: verifies version, path, health; auto-installs missing
  required deps; gracefully skips missing optional deps

#### Phase 3 — Workspace Bootstrap
- WorkspaceBootstrapper: creates 23 workspace directories
- Idempotent and restart-safe
- Custom installation paths supported
- Restore points created before every change
- Rollback protects user data (projects/, exports/, backups/)

#### Phase 4 — Database Bootstrap
- DatabaseBootstrapper: initializes 11 SQLite databases
- Schemas for audit, metrics, execution, mission, workflow, memory,
  knowledge_graph, experience, cognitive, engineering, research
- Pre-migration backups
- Integrity verification
- Idempotent migrations
- PostgreSQL and Qdrant detected when available

#### Phase 5 — Configuration Wizard
- ConfigurationWizard: generates a complete ConfigurationSpec
- 5 profiles: development, production, enterprise, minimal, portable
- 20+ configuration sections (storage, ports, providers, models, databases,
  memory, knowledge_graph, plugins, mcp, security, authentication, rbac,
  logging, telemetry, dashboard, api, cli, update_policy, backup_policy,
  recovery_policy, performance_profile)
- Interactive mode (returns prompts for CLI to render)
- Silent mode (applies profile defaults with no prompts)

#### Phase 6 — Provider Configuration
- ProviderConfigurator: discovers, validates, and configures 13 LLM providers
  (OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA, Groq,
  Mistral, Azure OpenAI, Ollama, LM Studio, custom)
- Validates every configured provider before enabling
- Disables failing providers automatically while installation continues
- API keys never written to disk (only api_key_set flag)
- Fallback routing configuration
- Local provider auto-discovery (Ollama, LM Studio)

#### Phase 7 — Agent Bootstrap
- AgentBootstrapper: discovers, validates, registers, and manifests 8 agents
  (Claude Code, OpenCode, Hermes, Codex CLI, Gemini CLI, OpenHands, Cline,
  Roo Code)
- Capability indexing
- Manifest generation (1.0 schema)
- Automatic registration (no manual registration required)
- Install missing agents when can_install=True

#### Installer Orchestrator
- InstallerOrchestrator: top-level facade running all 7 phases
- Idempotent, restart-safe, transactional, rollback-capable
- 11 installation modes: interactive, silent, minimal, developer, enterprise,
  portable, offline, repair, force, upgrade, validate
- Restore point created before every install
- Full installation report saved to workspace

#### Installer Scripts
- deploy/windows/install.ps1: PowerShell one-click installer
  (`irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex`)
- deploy/linux/install.sh: Bash one-click installer
  (`curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/linux/install.sh | bash`)
- All scripts support all 11 installation modes

#### CLI Integration
- New `aaios install` command group with 11 subcommands
- `aaios install` (interactive by default)
- `aaios install --silent|--minimal|--developer|--enterprise|--portable|--offline|--repair|--force|--upgrade|--validate`
- All commands support `--workspace`, `--profile`, `--force`

#### API Integration
- 7 new REST endpoints under `/api/v1/installer/`:
  - POST /environment — detect host environment
  - POST /install — run the installer
  - POST /validate — validate an existing installation
  - POST /repair — repair an existing installation
  - GET /dependencies — list all known dependencies
  - GET /providers — list all supported providers
  - GET /agents — list all supported agents

#### Tests
- 62 new tests in tests/unit/test_installer.py
- Covers all 7 phases + the orchestrator
- Total tests: 1338 (1282 unit + 56 integration/security/e2e/stress/perf)

#### Architecture
- INV-02: services/installer/ is exempted (system-level tool that
  legitimately needs subprocess to detect and install dependencies)
- INV-09: services/installer/ is exempted (legitimately needs agent names
  to discover them)
- All other invariants maintained

#### Quality Gates
- Ruff: clean
- Mypy --strict: clean (264 source files)
- Bandit: no Medium/High severity on installer code
- Pytest: 1338/1338 passing

#### Backward Compatibility
- 100% backward compatible with v5.3.1-LTS
- No API changes
- No data format changes

### Enterprise Validation, Self-Healing, Backup, Recovery & Update Management (Part 2)

Adds self-healing diagnostics, encrypted transactional backups, continuous monitoring, and automated upgrade/rollback channels.

#### Phase 8 — Enterprise Doctor
- DoctorManager: executes 20+ diagnostic scans (Quick, Full, Offline, Database, API, CLI, etc.)
- Health, Production, Risk, Performance, and Availability Scores calculation

#### Phase 9 — Self-Healing Engine
- SelfHealingEngine: automatically resolves configuration drift, boots missing directory trees, bootstraps sqlite schemas, and restricts secrets directory permissions

#### Phase 10 — Backup System
- BackupManager: creates full, incremental, and differential backups under AES-128 bit Fernet symmetric encryption

#### Phase 11 — Disaster Recovery
- RecoveryManager: restores workspace files safely with pre-restore transactional checkpoints and rollbacks on integrity validation errors

#### Phase 13 — Update Manager
- UpdateManager: downloads delta packages, pins version releases, and coordinates update channel migrations (LTS, Stable, Beta, Nightly)

#### Phase 14 & 15 — Release Validator & Continuous Monitoring
- ReleaseValidator: checks type safety, latency constraints, and outputs readiness scores
- ContinuousHealthMonitor: tracks CPU, RAM, disk, latency, and sends Discord, Slack, and console alerts

### Uninstall, Cleanup, Factory Reset, Release Packaging & Production Validation (Part 3)

Completes the operational lifecycle with packaging, certification, benchmarks, and clean uninstalls.

#### Phase 16 — Enterprise Uninstall
- UninstallManager: stops background worker processes, drops service tasks, and prunes code, environment, or data packages

#### Phase 17 — Factory Reset
- ResetManager: wipes active system configurations, database tables, and memory vector indices after generating safety recovery snapshots

#### Phase 18 — Cleanup Manager
- CleanupManager: prunes temporary files, package stores, caches, and legacy log rotations to reclaim disk space

#### Phase 19 — Packaging
- PackagingManager: bundles Portable, Zip, Developer, Offline Installer, and Enterprise zip packages, generating SHA-256/SHA-512 checklists and CycloneDX SBOMs

#### Phase 20 — Production Validation Matrix
- CertifyManager: executes comprehensive validation checklists and generates compliance certificates

#### Phase 21 — Performance Benchmark
- BenchmarkManager: measures cold/warm boot speeds, database latencies, recalls, and CPU/RAM footprints

## [5.3.1-LTS] — 2026-07-16

### Enterprise LTS Certification & Production Freeze

This is a **production hardening release**. No new features. No breaking
changes. Pure stability, maintainability, observability, documentation,
and certification work.

#### Code Quality
- Fixed 62 pre-existing mypy errors in `surfaces/api/app.py` and
  `surfaces/cli/__main__.py` via proper `cast()` annotations
- Removed bare `except Exception` in CLI helpers; now uses `httpx.HTTPError`
- `_api_get()` now accepts an optional `params` keyword argument
- Ruff: 100% clean across the entire codebase
- Mypy --strict: 100% clean across 254 source files
- Bandit: no Medium/High severity findings
- Pytest: 1220/1220 passing

#### LTS Audit Tooling
- `scripts/lts/audit.py` — repository audit (architecture, layering, dead code, duplicates, security)
- `scripts/lts/benchmark.py` — performance benchmarks across kernel, supervisor, research, engineering, CLI
- `scripts/lts/security.py` — security certification (secrets, auth, RBAC, sandbox, SBOM, threat model)
- `scripts/lts/coverage.py` — coverage aggregator
- `scripts/lts/docs.py` — documentation completeness audit
- All scripts write JSON reports to `lts-audit/`

#### Performance Certification
- 11 benchmarks across 5 categories (kernel, supervisor, research, engineering, CLI)
- 10/11 passing (90.91%)
- All v5.2 and v5.3 modules benchmark under 2ms per operation

#### Security Certification
- 0 hardcoded secrets detected
- RBAC, EncryptedSecretStore, and AuditLog all present
- SBOM generated: 45 dependencies cataloged
- STRIDE threat model: 7 threats with mitigations
- Overall risk: high (CORS wildcard — documented, deferred to v5.3.2)

#### Documentation
- 100% documentation completeness (16/16 required docs present)
- Updated SUPPORT.md with LTS policy and supported version matrix
- Release notes and migration guides for all v5.x versions

#### LTS Policy
- 12 months full support (until 2027-07-16)
- 12 months extended security support (until 2028-07-16)
- See SUPPORT.md for the full policy

#### Known Issues
1. CORS wildcard in API — documented, deferred to v5.3.2
2. No rate limiting on API — documented, deferred to v5.3.2
3. Some pre-v5.2 modules have lower test coverage

#### Backward Compatibility
- 100% backward compatible with v5.3.0
- No API changes
- No data format changes
- No config changes

## [5.3.0] — 2026-07-16

### Enterprise Research & Reasoning Platform

#### Phase 1 — Enterprise Research Engine
- Research Projects, Sessions, Plans, Tasks, Pipelines
- Research History, Templates, Memory, Workspace, Timeline
- Full lifecycle management with audit trail

#### Phase 2 — Multi-Agent Research (10 Specialized Agents)
- Literature, Scientific, Legal, Business, Technology, Market, News, Financial, Policy, Open Data agents
- Each agent produces structured findings with confidence, evidence, limitations, and follow-up questions
- ResearchAgentOrganization with heuristic agent selection

#### Phase 3 — Multi-Model Reasoning
- Independent analysis from multiple LLMs
- Conflict detection (negation, numerical disagreement)
- Consensus generation with confidence scoring
- Minority opinion recording
- Evidence ranking by model confidence and provider reliability
- Explainable reasoning process

#### Phase 4 — Evidence Graph
- 6 node types: claim, fact, source, document, report, session
- 5 edge types: support, contradiction, dependency, reference, citation
- Evidence strength computation
- Searchable graph with neighbor traversal

#### Phase 5 — Fact Verification
- Cross-reference multiple sources
- Stance classification (supports / contradicts / neutral)
- Source reliability ranking (5 tiers)
- Verification status: verified, partially_verified, contradicted, unverified, unverifiable
- Verification reports with confidence, evidence, and source ranking

#### Phase 6 — Knowledge Synthesis
- 9 standard sections: executive summary, technical summary, timeline, entities, relationships, decision support, insights, recommendations, open questions
- Entity extraction via capitalized n-grams, dates, and metric detection
- Relationship map via entity co-occurrence
- Overall confidence from section confidence and source reliability

#### CLI Integration
- New `aaios research` command group (11 subcommands)
- All commands support `--format json|yaml|markdown|table`

#### API Integration
- 13 new REST endpoints under `/api/v1/research/`
- OpenAPI auto-generated

#### Dashboard Integration
- New `/research` page with platform overview and agent registry
- Dark/light mode aware, responsive

#### Quality Gates
- Ruff: clean
- Mypy --strict on services/research/: clean (9 source files)
- Bandit: no Medium/High severity
- Pytest: 1220/1220 passing (1138 pre-existing + 82 new)
- Architecture invariants (INV-02, INV-09): enforced
- Backward compatible with v5.2

## [5.2.0] — 2026-07-16

### Autonomous Software Engineering Platform — Complete

#### Phase 17 — Engineering Review Engine
- 12 review types: architecture, code, security, performance, dependency, documentation, testing, API, database, workflow, plugin, mission
- Every review produces: summary, strengths, weaknesses, observations, evidence, risk score, confidence, recommendations, approval requirement, historical comparison
- READ-ONLY — never modifies code

#### Phase 18 — Test Intelligence Engine
- Analyzes unit/integration/e2e/performance/stress/security/mutation tests
- Detects flaky tests, long-running tests, missing tests, duplicate tests, unused fixtures
- Generates coverage reports, risk reports, recommended test cases (engineer writes them — never auto-generates code)
- Computes mutation readiness score and regression predictions

#### Phase 19 — Documentation Intelligence
- Continuously analyzes README, architecture, developer, API, CLI, SDK, migration, release notes, user manuals
- Detects outdated, missing, broken-reference, unused pages, missing examples
- Computes completeness score, consistency score, documentation coverage %

#### Phase 20 — Repository Evolution Engine
- Tracks commits, branches, releases, tags
- Generates timeline, evolution dashboard, growth analytics, historical comparisons
- Uses new `core/gateway/git.py` (GitGateway) — read-only, whitelisted git commands (INV-02 compliant)

#### Phase 21 — Release Readiness Engine
- 10 readiness dimensions: architecture compliance, security, performance, testing, documentation, packaging, dependencies, migration, compatibility, operational readiness
- Go / Conditional-Go / No-Go recommendation
- Certification report (none / basic / standard / strict) and required approvals list

#### Phase 22 — Developer Productivity Engine
- DORA metrics (deployment frequency, lead time, change failure rate, recovery time)
- Cycle time, review time, planning accuracy, testing efficiency, documentation completion
- Classifies team as Low / Medium / High / Elite
- Productivity dashboards with weekly trends and optimization opportunities

#### Phase 23 — Repository Health Center
- 8 health dimensions: repository, architecture, dependency, documentation, security, testing, release, knowledge
- Weighted overall score, 12-point trend history, prioritized improvement recommendations

#### Phase 24 — Dashboard Integration
- 8 new pages: /engineering, /repository, /architecture, /reviews, /test-intelligence, /release-readiness, /repository-health, /features, /dependencies
- All pages: live updates, dark/light mode, responsive design

#### Phase 25 — CLI Integration
- 10 new command groups: engineering, architecture, review, metrics, repository, release, health, documentation, dependencies, planning
- All commands support --format json|yaml|markdown|table

#### Phase 26 — API Integration
- 22 new REST endpoints under /api/v1/engineering/
- OpenAPI auto-generated

#### Infrastructure
- New `core/gateway/git.py` — GitGateway centralizing all git I/O (INV-02)
- 56 new tests in `tests/unit/test_engineering_part1b2.py`
- Total tests: 1138 passing (up from 1082)
- Total API endpoints: 174 (up from 152)
- Total CLI command groups: 23 (up from 13)

#### Quality Gates
- Ruff: clean
- Mypy --strict on services/engineering/: clean (14 source files)
- Bandit: 0 Medium/High severity on new code
- Pytest: 1138/1138 passing
- Architecture invariants (INV-02, INV-09): enforced

## [5.1.0] — 2026-07-16

### Enterprise Knowledge & Memory Platform

#### Knowledge Platform
- 15 memory types coordinated by MemoryOrchestrator (promote/demote/merge/compress)
- KnowledgePlatform with entries, versions, collections, workspaces
- HybridSearchEngine (TF-IDF + fuzzy)
- RetrievalEngine (RAG with citations, conflict detection, dedup)
- KnowledgeGovernance (RBAC, approval, legal hold)
- EnterpriseKnowledgeGraph (20+ node types)

#### Knowledge Intelligence
- KnowledgeIntelligenceEngine (gap/conflict/freshness/coverage/relationship detection)
- AutonomousLearningEngine (lessons from executions/approvals/feedback, playbooks)
- RecommendationEngine
- RepositoryIntelligenceEngine (AST analysis)
- DocumentIntelligence (Python/Markdown/JSON/CSV)
- QualityAssurance

## [5.0.0] — 2026-07-15

### Enterprise Cognitive Intelligence Platform

#### Cognitive Layer
- CognitiveExperience (20+ fields)
- CognitiveLearningEngine (explainable stats)
- CognitivePredictionEngine (7 types with explanations)
- CognitiveOptimizationEngine (4 types, never auto-applied)
- EnterpriseKnowledgeGraph (14 node types)
- ArchitectureIntelligence
- RepositoryIntelligence
- EnterpriseReporting
- CognitiveManager facade

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
