# AAiOS v5.2.0 — Release Notes

**Release Date:** 2026-07-16
**Codename:** Autonomous Software Engineering Platform — Complete
**License:** Apache-2.0

---

## Highlights

AAiOS v5.2.0 transforms the platform into a complete **Autonomous Software Engineering
Assistant** that helps engineers across the entire software lifecycle — explaining,
analyzing, reviewing, validating, and recommending — without ever silently modifying
production code.

Every recommendation requires human approval. Every review contains confidence and
evidence. Every prediction is explainable. Every metric is historically traceable.

This release completes Part 1A (already shipped) plus Part 1B-1 and Part 1B-2.

---

## What's New in v5.2.0 (Part 1B-2)

### Phase 17 — Engineering Review Engine

Twelve review types covering the entire engineering lifecycle:

| Review | What it checks |
|---|---|
| Architecture | Layer boundaries, coupling, god classes |
| Code | Complexity, dead code, bare excepts, long functions |
| Security | eval/exec, hardcoded secrets |
| Performance | Nested loops, blocking calls in async |
| Dependency | Count, pinning, license concerns |
| Documentation | README, docstring coverage, broken refs |
| Testing | Test-to-source ratio, marker usage |
| API | Versioning, error handling, schema |
| Database | Migrations, raw SQL detection |
| Workflow | CI/CD pipeline completeness |
| Plugin | Manifest presence, contract |
| Mission | Required fields, approvals, risk register |

Every review produces: summary, strengths, weaknesses, observations, evidence,
risk score (0–1), confidence, recommendations, approval requirement, and a
historical comparison against previous reviews of the same type.

### Phase 18 — Test Intelligence Engine

- Analyzes unit, integration, e2e, performance, stress, security, and mutation tests
- Detects flaky tests (random/time/network signals), long-running tests, missing
  tests, duplicate tests, and unused fixtures
- Generates coverage reports from `coverage.xml`, coverage heat maps, risk reports,
  and recommended test cases (engineer writes them — engine never generates code)
- Computes mutation readiness score
- Predicts regression hotspots

### Phase 19 — Documentation Intelligence

- Continuously analyzes README, architecture docs, developer guides, API docs,
  CLI docs, SDK docs, migration guides, release notes, and user manuals
- Detects outdated, missing, broken-reference, and unused pages
- Detects missing examples in technical docs
- Computes completeness score, consistency score, and documentation coverage %

### Phase 20 — Repository Evolution Engine

- Tracks commits, branches, releases, tags
- Computes bug-fix trend, feature-growth trend, technical-debt trend, performance trend
- Generates unified timeline (commits + releases + merges + breaking changes)
- Historical comparisons between releases (commits-between, days-between)
- Uses new `core/gateway/git.py` — a read-only, whitelisted GitGateway that
  satisfies INV-02 (no subprocess outside core/gateway/)

### Phase 21 — Release Readiness Engine

Ten readiness dimensions:

1. Architecture compliance
2. Security
3. Performance
4. Testing
5. Documentation
6. Packaging
7. Dependencies
8. Migration
9. Compatibility
10. Operational readiness

Each dimension produces a 0–1 score with status (pass/warning/fail), blocking
issues, warnings, evidence, and confidence. Aggregated into an overall score and
a Go / Conditional-Go / No-Go recommendation. Produces a certification report
(none / basic / standard / strict) and the list of required approvals.

### Phase 22 — Developer Productivity Engine

DORA metrics (deployment frequency, lead time, change failure rate, recovery
time) plus cycle time, review time, planning accuracy, testing efficiency, and
documentation completion. Classifies the team as Low / Medium / High / Elite
against standard DORA thresholds. Generates productivity dashboards with weekly
trends and optimization opportunities.

### Phase 23 — Repository Health Center

Eight health dimensions monitored continuously:

- Repository, Architecture, Dependency, Documentation, Security, Testing,
  Release, Knowledge

Each dimension produces a 0–100 score and status (healthy/warning/critical).
The overall score is a weighted average. Maintains a 12-point trend history per
run and generates prioritized improvement recommendations.

### Phase 24 — Dashboard Integration (8 new pages)

- `/engineering` — overview with cards linking to all subsystems
- `/repository` — analysis + evolution dashboard
- `/architecture` — recommendations with severity/confidence/risk
- `/reviews` — all 12 review types in one page
- `/test-intelligence` — coverage, flaky tests, mutation readiness
- `/release-readiness` — Go/No-Go banner, 10 dimensions, certifications
- `/repository-health` — overall score, 8 dimensions, trend chart
- `/features`, `/dependencies` — feature growth and dependency review

All pages support live updates, dark/light mode (via CSS variables), responsive
layout, and export-friendly rendering.

### Phase 25 — CLI Integration

Ten new CLI command groups, each supporting `--format json|yaml|markdown|table`:

```
aaios engineering   overview, agents, test-intelligence, productivity
aaios architecture  recommendations
aaios review        run <type> <target>, all <target>
aaios metrics       show
aaios repository    analyze, evolution, timeline
aaios release       readiness, certify
aaios health        show
aaios documentation analyze, recommendations
aaios dependencies  review
aaios planning      create, impact
```

### Phase 26 — API Integration

20+ new REST endpoints under `/api/v1/engineering/`:

- `/reviews`, `/reviews/{type}`, `/reviews/types`
- `/test-intelligence/{analysis,coverage,risk}`
- `/documentation/{analysis,recommendations}`
- `/repository/{analysis,evolution,timeline}`
- `/release/{readiness,certification}`
- `/productivity/{dashboard,metrics,dora,events,report}`
- `/health`, `/health/score`
- `/planning/{create,impact}`

All endpoints follow the existing API conventions (JSON in/out, FastAPI tags,
OpenAPI auto-generated). Audit logging continues to apply via the existing
`AuditLog` infrastructure.

---

## What Was Already in v5.2 Part 1A / 1B-1

- **RepositoryIntelligenceEngine** — discovery, analysis, health scoring
- **CodeIntelligenceEngine** — AST for Python, regex for 20 languages, complexity
- **ArchitectureIntelligenceEngine** — layer violations, circular deps, missing tests
- **EngineeringAgentOrganization** — 16 specialized engineering agents
- **CapabilityRegistry** — languages, frameworks, domains
- **EngineeringWorkspaceManager** — repository sessions
- **PlanningEngine** — WBS, critical path, milestone planning
- **MetricsEngine** — cyclomatic/cognitive complexity, Halstead, MI, debt, duplication
- **ArchitectureAnalysisEngine** — drift, layer violations, dependency inversion
- **ImpactAnalysisEngine** — affected modules, services, APIs, tests
- **RecommendationEngine** — 14 recommendation categories
- **RiskEngine** — 8 risk types

---

## Quality Gates

| Gate | Status |
|---|---|
| Ruff | ✅ Clean |
| Mypy --strict (engineering/) | ✅ Clean |
| Bandit | ✅ No Medium/High severity |
| Pytest | ✅ 1138/1138 passing |
| Architecture invariants (INV-02, INV-09) | ✅ Enforced |
| No placeholders, TODOs, FIXMEs | ✅ Verified |

Test count: 1138 passing (1082 pre-existing + 56 new for Part 1B-2).

---

## Architecture Invariants Maintained

1. ✅ Never auto-execute optimizations (`requires_approval=True`)
2. ✅ All predictions explainable (confidence + explanation + evidence)
3. ✅ All learning explainable (confidence + explanation + source events)
4. ✅ Architecture Intelligence is read-only (never modifies code)
5. ✅ Read-only extension model (extend through public interfaces)
6. ✅ No opaque ML (statistical aggregation, trend analysis, weighted scoring)
7. ✅ INV-02: no I/O imports outside `core/gateway/` (new `git.py` gateway)
8. ✅ INV-09: no agent implementation names in core code
9. ✅ Never generates production code automatically
10. ✅ Every recommendation contains evidence

---

## Breaking Changes

**None.** All v5.1 APIs, CLIs, and dashboards continue to work unchanged. The
v5.2 additions are purely additive.

---

## Migration Guide

No migration required. Existing v5.1 installations upgrade in-place:

```bash
pip install --upgrade aaios==5.2.0
```

The new engineering endpoints and CLI commands are available immediately. The
new dashboard pages are linked from the top navigation.

---

## Dependencies

New optional dependencies:
- `defusedxml` — for safe parsing of coverage XML
- `types-defusedxml` — for mypy stubs
- `PyYAML` + `types-PyYAML` — for YAML CLI output

All existing dependencies remain unchanged.

---

## Contributors

AAiOS Contributors — built as a single-engineer architecture exercise
demonstrating how an agentic operating system can serve as a peer to software
engineers rather than replacing them.

---

## License

Apache-2.0 — see `LICENSE`.
