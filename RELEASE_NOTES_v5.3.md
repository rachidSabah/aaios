# AAiOS v5.3.0 — Release Notes

**Release Date:** 2026-07-16
**Codename:** Enterprise Research & Reasoning Platform — Part 1A
**License:** Apache-2.0

---

## Highlights

AAiOS v5.3.0 transforms the platform into an **Enterprise Research Operating
System** capable of professional-grade research: gathering information,
verifying facts, comparing sources, detecting contradictions, reasoning across
multiple models, building knowledge, and explaining every conclusion.

Every conclusion contains evidence. Every claim has a confidence score. Every
export requires human approval. The platform never intentionally hallucinates —
when evidence is missing, it says so explicitly and produces low-confidence
output with documented limitations.

---

## What's New in v5.3.0

### Phase 1 — Enterprise Research Engine

A complete research lifecycle management system:

- **Research Projects** — top-level containers with objectives, research
  questions, domain, status, owner, collaborators, tags
- **Research Sessions** — individual research executions within a project,
  with scope (broad/focused/deep_dive), agent assignment, timing, models used
- **Research Plans** — methodology, agent assignments, timeline, expected
  outputs, risk assessment, confidence, reasoning
- **Research Tasks** — granular units with dependencies, priority, estimated
  and actual minutes, inputs and outputs
- **Research Pipelines** — multi-stage execution graphs with parallel/serial
  stages and inter-stage dependencies
- **Research History** — read-only view of past sessions, findings, timeline,
  and memory entries per project
- **Research Templates** — reusable project templates with recommended agents
  and pipelines; instantiate to create new projects
- **Research Memory** — persistent cross-project memory (findings, lessons,
  patterns, sources, methods) with confidence and access tracking
- **Research Workspace** — grouping of related projects with collaborators
- **Research Timeline** — append-only event log per project (created, started,
  completed, finding added, claim made, fact verified, etc.)

### Phase 2 — Multi-Agent Research (10 Specialized Agents)

| Agent | Domain | Default Reliability |
|---|---|---|
| Literature | Books, essays, literary criticism | Tier 3 (Established) |
| Scientific | Peer-reviewed papers, datasets, replications | Tier 1 (Peer-Reviewed) |
| Legal | Statutes, case law, regulations, treaties | Tier 2 (Official) |
| Business | Companies, industries, market positioning | Tier 3 (Established) |
| Technology | Specifications, RFCs, technical docs | Tier 2 (Official) |
| Market | Market size, segments, trends, forecasts | Tier 3 (Established) |
| News | Current events, press releases, journalism | Tier 3 (Established) |
| Financial | Prices, ratios, filings, macro indicators | Tier 2 (Official) |
| Policy | Government policy, regulations, impact analysis | Tier 2 (Official) |
| Open Data | Public datasets, statistics, government data | Tier 2 (Official) |

Each agent produces a structured finding with: title, summary, key points,
evidence, sources, confidence, limitations, and follow-up questions. Agents
never fabricate evidence — when source material is unavailable, they return
low-confidence findings with explicit limitations.

The `ResearchAgentOrganization` provides a registry, lookup by type, and
heuristic agent selection based on query keywords.

### Phase 3 — Multi-Model Reasoning

Multiple LLMs independently analyze the same question. The engine:

- Collects independent reasoning from each model
- Compares reasoning across models
- Detects conflicts (negation contradictions, numerical disagreements)
- Ranks evidence by model confidence and provider reliability
- Generates a consensus statement with confidence score
- Records minority opinions (low-confidence or low-overlap analyses)
- Produces a human-readable explanation of the entire reasoning process

When fewer than `min_models_for_consensus` (default 2) analyses are provided,
the engine explicitly notes that consensus cannot be formed and returns a
low-confidence result.

### Phase 4 — Evidence Graph

A searchable graph of research artifacts:

**Node types:** claim, fact, source, document, report, session

**Edge types:**
- `support` — node A supports node B
- `contradiction` — node A contradicts node B
- `dependency` — node A depends on node B
- `reference` — node A references node B
- `citation` — node A cites node B

Every edge carries an evidence strength weight (0–1). The graph supports:

- Node lookup by ID or reference
- Neighbor traversal in any direction
- Supporting/contradicting evidence lookup per claim
- Substring search across node labels
- Aggregate evidence strength computation (weighted support minus weighted contradiction)
- Statistics by node kind and edge type

### Phase 5 — Fact Verification

Cross-references multiple sources to verify a fact:

- Classifies each source's stance (supports / contradicts / neutral) via
  term-overlap and negation detection
- Ranks sources by reliability tier (Tier 1 Peer-Reviewed → Tier 5 Unverified)
  and per-source reliability score
- Computes a verification status: `verified`, `partially_verified`,
  `contradicted`, `unverified`, or `unverifiable`
- Produces a verification report with: status, confidence, sources checked
  / supporting / contradicting / neutral, source ranking, conflicts,
  explanation, verification timestamp
- Every verification requires human approval

### Phase 6 — Knowledge Synthesis

Merges multiple documents into unified knowledge with nine standard sections:

1. **Executive Summary** — top themes and primary source
2. **Technical Summary** — entities and detailed findings
3. **Timeline** — dated events from publication dates
4. **Entities** — extracted via capitalized n-grams, dates, and metric detection
5. **Relationship Map** — entity co-occurrence weighted graph
6. **Decision Support** — average reliability and sufficiency assessment
7. **Key Insights** — top entities by mention count
8. **Recommendations** — corpus gaps and verification needs
9. **Open Questions** — knowledge gaps and follow-up research

Every section carries confidence, evidence, and source references. The
overall synthesis confidence is a weighted blend of section confidence and
source reliability. Synthesis is never auto-published.

---

## CLI Integration

New `aaios research` command group:

```
aaios research overview              # Platform overview
aaios research projects              # List projects (--status, --domain filters)
aaios research create-project        # Create a new project (--title, --description, --domain, --owner)
aaios research agents                # List the 10 specialized agents
aaios research research <type> <q>   # Run research with a specific agent
aaios research reason <question>     # Multi-model reasoning
aaios research evidence              # Evidence graph statistics
aaios research verify <fact>         # Fact verification
aaios research synthesize            # Knowledge synthesis
aaios research timeline              # Research timeline
aaios research stats                 # Engine statistics
```

All commands support `--format json|yaml|markdown|table`.

---

## API Integration

13 new REST endpoints under `/api/v1/research/`:

- `GET /overview` — platform overview
- `GET /projects`, `POST /projects`, `GET /projects/{id}` — project CRUD
- `GET /agents` — list the 10 agents
- `POST /agents/{type}/research` — run research with an agent
- `POST /reasoning` — multi-model reasoning
- `GET /evidence-graph`, `GET /evidence-graph/search` — evidence graph
- `POST /verification` — fact verification
- `POST /synthesis` — knowledge synthesis
- `GET /timeline` — research timeline
- `GET /stats` — engine statistics

OpenAPI schema auto-generated at `/docs`.

---

## Dashboard Integration

New `/research` page showing:

- Engine metrics (projects, sessions, plans, tasks, pipelines, templates,
  memory, findings)
- Evidence graph stats (nodes, edges, claims, facts, sources)
- All 10 specialized agents with display name, description, and reliability tier

Linked from the top navigation. Dark/light mode aware. Responsive layout.

---

## Architecture Invariants Maintained

1. ✅ Every conclusion contains evidence
2. ✅ Every claim has a confidence score
3. ✅ Every export requires human approval
4. ✅ No intentional hallucination — missing evidence is documented
5. ✅ All services are read-only with respect to external systems
6. ✅ Never auto-publishes — human approval required for exported reports
7. ✅ INV-02: no I/O imports outside `core/gateway/`
8. ✅ INV-09: no agent names in core code
9. ✅ Backward compatible — v5.2 APIs, CLIs, and dashboards unchanged

---

## Quality Gates

| Gate | Status |
|---|---|
| Ruff | ✅ Clean |
| Mypy --strict on services/research/ | ✅ Clean (9 source files) |
| Bandit | ✅ No Medium/High severity |
| Pytest | ✅ 1220/1220 passing |
| Architecture invariants | ✅ Enforced |

Test count: 1220 passing (1138 pre-existing + 82 new for v5.3).

---

## Breaking Changes

**None.** All v5.2 APIs, CLIs, and dashboards continue to work unchanged.
v5.3 is purely additive.

---

## Migration Guide

No migration required:

```bash
pip install --upgrade aaios==5.3.0
```

The new research endpoints and CLI commands are available immediately. The
new dashboard page is linked from the top navigation.

---

## Module Summary

| Module | Purpose | LOC |
|---|---|---|
| `services/research/models.py` | All dataclasses for the research platform | 700+ |
| `services/research/engine.py` | Phase 1 — Research Engine | 450+ |
| `services/research/agents.py` | Phase 2 — 10 specialized agents + organization | 400+ |
| `services/research/multi_model.py` | Phase 3 — Multi-Model Reasoning | 220+ |
| `services/research/evidence_graph.py` | Phase 4 — Evidence Graph | 330+ |
| `services/research/verification.py` | Phase 5 — Fact Verification | 240+ |
| `services/research/synthesis.py` | Phase 6 — Knowledge Synthesis | 460+ |
| `services/research/manager.py` | ResearchManager facade | 230+ |
| `tests/unit/test_research.py` | 82 tests across all phases | 640+ |

Total: ~3600 lines of new production code + ~640 lines of tests.

---

## License

Apache-2.0 — see `LICENSE`.
