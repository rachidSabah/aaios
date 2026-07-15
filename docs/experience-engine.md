# Experience & Learning Engine — Architecture & Developer Guide

**Version:** 2.1
**Status:** Production Ready
**Subsystem:** `services/experience/`

## Overview

The Experience & Learning Engine is a modular subsystem that captures every
task execution as an immutable **ExperienceRecord**, indexes them for semantic
search, mines them for patterns, and computes reliability scores that feed
adaptive routing decisions.

The system **learns from every execution** — no machine-learning training
required. It's an evidence-based reasoning engine that accumulates operational
experience and uses it to make better decisions over time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LearningEngine (facade)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Collector   │→ │  Store   │→ │ Indexer  │  │  Retriever  │  │
│  │ (events)    │  │ (JSON)   │  │ (TF-IDF) │  │ (search)    │  │
│  └─────────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│       ↑                ↑              ↑               ↑         │
│       │                │              │               │         │
│  ┌────┴────┐    ┌──────┴──────┐ ┌────┴────┐   ┌──────┴──────┐  │
│  │ Event   │    │  Analyzer   │ │ Scorer  │   │  Replayer   │  │
│  │ Bus     │    │ (patterns)  │ │ (reliab)│   │  (replay)   │  │
│  └─────────┘    └─────────────┘ └─────────┘   └─────────────┘  │
│                       │                                 │       │
│  ┌────────────┐  ┌────┴──────┐  ┌──────────┐  ┌────────┴────┐  │
│  │ Exporter   │  │ Compressor│  │Retention │  │  API + CLI  │  │
│  │ (JSON/CSV) │  │ (merge)   │  │ Manager  │  │  + Dashboard│  │
│  └────────────┘  └───────────┘  └──────────┘  └─────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. ExperienceRecord (models.py)

Immutable frozen dataclass capturing the full lifecycle of a task:

| Field | Type | Description |
|---|---|---|
| `experience_id` | UUID | Unique identifier |
| `timestamp` | datetime | When the experience occurred |
| `task_id` | UUID | The task that was executed |
| `agent_id` | str | Which agent served it |
| `agent_type` | str | Agent type (coding, desktop, etc.) |
| `provider` | str \| None | LLM provider used |
| `model` | str \| None | Specific model used |
| `capabilities_used` | list[str] | Capability namespaces invoked |
| `goal` | str | The natural-language goal |
| `plan` | list[ExecutionStep] | The execution plan |
| `input_summary` | str | Input context summary |
| `output_summary` | str | Output result summary |
| `execution_time_s` | float | Wall-clock execution time |
| `latency_s` | float | End-to-end latency |
| `retries` | int | Number of retries |
| `reflection_score` | float | Self-reflection quality (0.0-1.0) |
| `qa_score` | float | QA evaluation quality (0.0-1.0) |
| `user_feedback` | UserFeedback | User rating + comment |
| `outcome` | str | success / failure / partial / cancelled / timeout |
| `success` | bool | Whether the task succeeded |
| `failure_reason` | str \| None | Why it failed |
| `recovery_action` | str \| None | How it was recovered |
| `resource_usage` | ResourceUsage | CPU, memory, disk, network |
| `cost_usd` | float | Total cost |
| `token_usage` | TokenUsage | Input/output/reasoning tokens |
| `confidence` | float | Agent confidence (0.0-1.0) |
| `context_hash` | str | SHA-256 hash of agent+goal+input |
| `knowledge_references` | list[KnowledgeRef] | Memory items used |
| `artifacts_produced` | list[ArtifactRef] | Artifacts created |

### 2. ExperienceStore (store.py)

Persistent JSON storage with in-memory indices.

- **Persistence:** One JSON file per record in `storage_dir`
- **Indices:** By agent_id, provider, capability, outcome, workflow_id, context_hash
- **Thread-safe:** asyncio.Lock around all operations
- **Queries:** Filter by any combination of fields, with pagination
- **Aggregations:** `summarize()` returns ExperienceSummary (success rate, avg quality, total cost, etc.)

### 3. ExperienceCollector (collector.py)

Subscribes to the event bus and builds records from live events.

**Subscribed topics:**
- `task.submitted` — start tracking a new execution
- `agent.dispatched` — record which agent + provider was used
- `agent.completed` — record outcome + cost + tokens
- `step.started` / `step.completed` — build the execution plan
- `task.completed` — finalize and store the record
- `experience.feedback` — apply user feedback

The collector maintains in-flight state (`InFlightExecution`) per task,
accumulating events until the task completes, then flushes a complete
ExperienceRecord to the store.

### 4. ExperienceIndexer (retriever.py)

Builds a TF-IDF index over all experience text fields (goal, input_summary,
output_summary, capabilities, failure_reason, agent_type).

- **Tokenization:** Lowercase, stop-word removal, regex word splitting
- **Scoring:** TF-IDF with document-length normalization
- **Rebuild:** Call `await indexer.rebuild()` to refresh the index
- **Search:** Returns ranked `SearchResult` list with matched terms

### 5. ExperienceRetriever (retriever.py)

High-level retrieval interface with pre-defined search types:

| SearchType | Description |
|---|---|
| `SIMILAR_SUCCESSES` | Find successful experiences similar to a query |
| `SIMILAR_FAILURES` | Find failed experiences (for debugging) |
| `BEST_AGENT_FOR_CAPABILITY` | Rank agents for a capability |
| `FASTEST_PROVIDER` | Providers with lowest avg latency |
| `CHEAPEST_PROVIDER` | Providers with lowest avg cost |
| `HIGHEST_QUALITY` | Workflows with highest avg quality |

### 6. ExperienceAnalyzer (analyzer.py)

Mines the store for patterns:

- **Success patterns:** Agent+capability combos that consistently succeed (≥3 successes)
- **Failure patterns:** Repeated failure reasons (≥2 occurrences)
- **Repeated fixes:** Recovery actions that consistently work
- **Trends:** Success rate over time (daily/hourly buckets)
- **LearningStats:** Top-level statistics (totals, rates, counts)

### 7. ExperienceScorer (analyzer.py)

Computes reliability scores (0.0-1.0) from historical evidence:

- **Agent reliability:** 50% success rate + 30% quality + 20% recent performance
- **Provider reliability:** 60% success + 25% latency (inverted) + 15% retry rate (inverted)
- **Capability reliability:** Success rate + best agent identification
- **Recommendations:** `recommend_agent_for_capability()` returns the best agent + reason

Trend detection: compares recent (last 10) success rate to overall, classifies
as `improving`, `declining`, or `stable`.

### 8. ExperienceReplayer (replayer.py)

Replays past experiences in three modes:

| Mode | Description |
|---|---|
| `DRY_RUN` | Return the original outcome without re-executing |
| `RE_EXECUTE` | Re-run with the original agent (requires executor) |
| `COMPARE` | Re-run with a different agent and compare |

### 9. ExperienceExporter (lifecycle.py)

Exports experiences to JSON or CSV for external analysis.

### 10. ExperienceCompressor (lifecycle.py)

Merges similar experiences (same context_hash + agent + capability) into
summary records. Keeps the most representative one, deletes the rest,
returns `CompressedExperience` summaries.

### 11. ExperienceRetentionManager (lifecycle.py)

Enforces retention policies:

- **Max age:** Delete records older than `max_age_days` (default 90)
- **Max total:** Enforce `max_total_records` (default 100,000)
- **Compress first:** Optionally compress before deleting

## Integration Points

The Experience & Learning Engine integrates with the existing AAiOS
architecture without breaking backward compatibility:

### Event Bus (no changes)
The collector subscribes to existing event topics (`task.*`, `agent.*`,
`step.*`). No new events are required — the engine listens to what's
already being published.

### Supervisor (read-only integration)
The Supervisor can query the LearningEngine for routing recommendations:
```python
recommendation = await engine.recommend_agent_for_capability("code.generate")
if recommendation:
    agent_id = recommendation["recommended_agent_id"]
```

### Planner (read-only integration)
The Planner can search for similar past workflows:
```python
results = await engine.search("python debugging", search_type="similar_successes")
```

### Reflection Agent (write integration)
After reflecting on a task, the Reflection Agent publishes a
`experience.feedback` event with the reflection score. The collector
applies it to the stored record.

### QA Agent (write integration)
Same as Reflection — publishes `experience.feedback` with the QA score.

### Model Router (read-only integration)
The Model Router can query provider reliability:
```python
rankings = await engine.rank_providers()
```

### Memory Manager (cross-reference)
Experience records can reference memory items used during execution
via `knowledge_references`. This enables tracing which memories
contributed to which outcomes.

### Dashboard (new pages)
- `/experience` — Experience Explorer (filterable table of all experiences)
- `/learning` — Learning Analytics (KPIs, agent/provider rankings, patterns)

### API (9 new endpoints)
- `GET /api/v1/experience` — list with filtering
- `GET /api/v1/experience/{id}` — get by ID
- `POST /api/v1/experience` — manual record
- `POST /api/v1/experience/search` — semantic search
- `POST /api/v1/experience/{id}/replay` — replay
- `GET /api/v1/experience/export/{format}` — JSON/CSV export
- `GET /api/v1/learning/stats` — top-level stats
- `GET /api/v1/learning/trends` — time-series
- `GET /api/v1/learning/agents` — agent rankings
- `GET /api/v1/learning/providers` — provider rankings
- `GET /api/v1/learning/workflows` — workflow rankings
- `GET /api/v1/learning/patterns` — pattern discovery
- `GET /api/v1/learning/recommendations/{capability}` — agent recommendation

### CLI (7 new commands)
- `aaios experience list` — list experiences
- `aaios experience show <id>` — show details
- `aaios experience search <query>` — semantic search
- `aaios experience replay <id>` — replay
- `aaios experience export <format>` — export
- `aaios learning stats` — learning statistics
- `aaios learning analyze` — pattern analysis
- `aaios learning agents` — agent rankings
- `aaios learning providers` — provider rankings
- `aaios learning recommend <capability>` — agent recommendation

## Sequence Diagrams

### Task Execution → Experience Capture

```
User    Supervisor   Agent    EventBus    Collector    Store
 │           │          │         │            │          │
 │─run──────▶│          │         │            │          │
 │           │─dispatch─▶         │            │          │
 │           │          │─started─▶            │          │
 │           │          │         │─task.submitted───────▶│
 │           │          │         │            │─create───▶│
 │           │          │         │            │  InFlight │
 │           │          │         │            │          │
 │           │          │─complete─▶           │          │
 │           │          │         │─agent.completed──────▶│
 │           │          │         │            │─update───│
 │           │          │         │            │  InFlight │
 │           │          │         │            │          │
 │           │─done─────│         │            │          │
 │           │          │         │─task.completed───────▶│
 │           │          │         │            │─flush────▶│
 │           │          │         │            │  Record  │
 │           │          │         │            │─store────▶│
```

### Adaptive Routing with Experience

```
User    Supervisor   LearningEngine    Agent
 │           │            │              │
 │─run──────▶│            │              │
 │           │─recommend─▶│              │
 │           │            │─query store─▶│
 │           │            │─score───────▶│
 │           │◀─agent_id──│              │
 │           │─dispatch──────────────────▶│
 │           │            │              │
 │           │─complete───│              │
 │           │            │─store────────▶│
 │           │            │  new record  │
```

### Semantic Search

```
User    API    LearningEngine    Indexer    Store
 │       │          │              │          │
 │─search▶│         │              │          │
 │       │─search──▶│              │          │
 │       │          │─rebuild──────▶│          │
 │       │          │              │─all─────▶│
 │       │          │              │◀─records─│
 │       │          │              │─index───│
 │       │          │─search──────▶│          │
 │       │          │              │─tfidf───│
 │       │          │◀─results─────│          │
 │       │◀─results─│              │          │
 │◀─json──│         │              │          │
```

## Class Diagram

```
┌─────────────────────┐
│  ExperienceRecord   │ (frozen dataclass)
│  ─────────────────  │
│  + experience_id    │
│  + task_id          │
│  + agent_id         │
│  + outcome          │
│  + quality_score()  │
│  + to_dict()        │
│  + from_dict()      │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│  ExperienceStore    │────▶│  ExperienceFilter   │
│  ─────────────────  │     └─────────────────────┘
│  + store()          │
│  + get()            │     ┌─────────────────────┐
│  + query()          │────▶│  ExperienceSummary  │
│  + summarize()      │     └─────────────────────┘
│  + delete()         │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│ ExperienceCollector │     │  ExperienceIndexer  │
│ ─────────────────── │     │  ─────────────────  │
│ + subscribe()       │     │  + rebuild()        │
│ + _handle_event()   │     │  + search()         │
│ + _flush()          │     │  + _tfidf()         │
└─────────────────────┘     └─────────────────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │ ExperienceRetriever │
                            │ ─────────────────── │
                            │ + similar()         │
                            │ + best_agent_for()  │
                            │ + fastest_provider()│
                            │ + cheapest_provider()│
                            └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│ ExperienceAnalyzer  │     │  ExperienceScorer   │
│ ─────────────────── │     │  ─────────────────  │
│ + learning_stats()  │     │ + score_agent()     │
│ + discover_patterns │     │ + score_provider()  │
│ + trend_over_time() │     │ + rank_agents()     │
└─────────────────────┘     │ + recommend_agent() │
                            └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│ ExperienceReplayer  │     │  ExperienceExporter │
│ ─────────────────── │     │  ─────────────────  │
│ + replay()          │     │ + export_json()     │
│   - dry_run         │     │ + export_csv()      │
│   - re_execute      │     └─────────────────────┘
│   - compare         │
└─────────────────────┘     ┌─────────────────────┐
                            │ ExperienceCompressor│
┌─────────────────────┐     │  ─────────────────  │
│ExperienceRetention  │     │ + compress()        │
│      Manager        │     └─────────────────────┘
│ ─────────────────── │
│ + enforce()         │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐
│   LearningEngine    │ (facade)
│  ─────────────────  │
│  + store            │
│  + collector        │
│  + indexer          │
│  + retriever        │
│  + analyzer         │
│  + scorer           │
│  + replayer         │
│  + exporter         │
│  + compressor       │
│  + retention        │
│  ─────────────────  │
│  + start()          │
│  + record()         │
│  + search()         │
│  + learning_stats() │
│  + rank_agents()    │
│  + recommend()      │
└─────────────────────┘
```

## Developer Guide

### Adding a new experience field

1. Add the field to `ExperienceRecord` in `models.py` (with a default)
2. Update `to_dict()` and `from_dict()` to serialize it
3. Add a filter field to `ExperienceFilter` in `store.py` if queryable
4. Update `ExperienceFilter.matches()` if the filter is added
5. Add a test in `test_experience.py`

### Adding a new search type

1. Add the type string to `SearchType` in `retriever.py`
2. Implement the search method on `ExperienceRetriever`
3. Add a case to `ExperienceRetriever.search()` for the new type
4. Add a test

### Adding a new pattern discovery

1. Add a method to `ExperienceAnalyzer`
2. Add the result type as a dataclass
3. Wire it into `PatternReport` if it's a pattern type
4. Add a test

### Adding a new scoring dimension

1. Add the dimension to the relevant reliability dataclass (`AgentReliability`, etc.)
2. Update the scoring formula in `ExperienceScorer`
3. Add a test

## Performance Characteristics

Based on Phase 9 benchmarks (see `download/release/phase9_perf.json`):

| Operation | Throughput |
|---|---|
| Store record | ~10,000/s |
| Query with filter | ~50,000/s |
| Index rebuild (1000 records) | ~500ms |
| TF-IDF search | ~5ms per query |
| Pattern discovery (1000 records) | ~100ms |
| Reliability scoring | ~1ms per agent |

## Retention & Compression

Default retention policy:
- Max age: 90 days
- Max total records: 100,000
- Compress before delete: true

Compression groups records by (context_hash, agent_id, capability) and keeps
only the most representative one when ≥5 similar records exist.

To customize:
```python
from services.experience import LearningEngine, RetentionPolicy

engine = LearningEngine(
    storage_dir=Path("/var/lib/aaios/experience"),
    retention_policy=RetentionPolicy(
        max_age_days=365,
        max_total_records=1_000_000,
        compress_before_delete=True,
    ),
)
```

## Testing

```bash
# Run all experience tests
python -m pytest tests/unit/test_experience.py -v

# Run with coverage
python -m pytest tests/unit/test_experience.py --cov=services/experience

# Run stress tests only
python -m pytest tests/unit/test_experience.py::TestExperienceStress -v
```

Test coverage: 75 tests across 11 test classes:
- `TestExperienceRecord` (7 tests) — model immutability, serialization, quality scoring
- `TestExperienceStore` (13 tests) — CRUD, filtering, pagination, persistence
- `TestExperienceCollector` (4 tests) — event bus subscription, lifecycle tracking
- `TestExperienceIndexer` (3 tests) — TF-IDF indexing, search relevance
- `TestExperienceRetriever` (7 tests) — all search types
- `TestExperienceAnalyzer` (3 tests) — stats, patterns, trends
- `TestExperienceScorer` (7 tests) — reliability scores, rankings, recommendations
- `TestExperienceReplayer` (5 tests) — all replay modes
- `TestExperienceExporter` (3 tests) — JSON/CSV export
- `TestExperienceCompressor` (1 test) — compression
- `TestExperienceRetentionManager` (2 tests) — retention enforcement
- `TestLearningEngine` (12 tests) — facade integration
- `TestExperienceIntegration` (1 test) — end-to-end lifecycle
- `TestExperienceStress` (3 tests) — 1000 records, 500 index, concurrent stores

## File Manifest

```
services/experience/
├── __init__.py          # Public API exports
├── models.py            # ExperienceRecord + supporting types
├── store.py             # ExperienceStore + ExperienceFilter + ExperienceSummary
├── collector.py         # ExperienceCollector (event-bus subscriber)
├── retriever.py         # ExperienceIndexer + ExperienceRetriever + SearchResult
├── analyzer.py          # ExperienceAnalyzer + ExperienceScorer + pattern types
├── replayer.py          # ExperienceReplayer + ReplayResult
├── lifecycle.py         # Exporter + Compressor + RetentionManager
└── engine.py            # LearningEngine facade

tests/unit/
└── test_experience.py   # 75 tests

surfaces/api/
└── app.py               # +13 new endpoints (experience + learning)

surfaces/cli/
└── __main__.py          # +10 new commands (experience + learning subcommands)

surfaces/web/src/app/
├── experience/page.tsx  # Experience Explorer
└── learning/page.tsx    # Learning Analytics
```
