# 01 — Goals & Design Principles

> **Audience:** implementers and reviewers.
> **Purpose:** pin down the non-negotiable design invariants before any code is written, so that every later trade-off can be evaluated against them.

---

## 1. Primary goals

The system exists to achieve five concrete outcomes. Every architectural decision must be traceable to at least one of them.

### 1.1 Poly-model orchestration
The user must never be locked into a single LLM provider. The system must support at least ten providers (OpenRouter, OpenAI, Anthropic, Google, Mistral, DeepSeek, GLM, NVIDIA, Ollama, LM Studio) plus custom OpenAI-compatible endpoints, and must allow per-task routing, automatic failover, and side-by-side cost comparison. A provider going down, deprecating a model, or changing its pricing must never require a code change in the supervisor or the agents.

### 1.2 Agent composition
The system must allow multiple specialized agents (Claude Code for engineering, Hermes for desktop, plus Research, Browser, Memory, QA, Reflection, Planner) to collaborate on a single user goal under a single supervisor. Agents must be independently deployable, independently versioned, and replaceable. Adding a new agent must not require modifying the supervisor.

### 1.3 Long-horizon autonomy
The system must be able to execute multi-step, multi-hour tasks (e.g., "research this topic, write a report, file three issues, open a PR, and notify me on Slack when done") without human intervention, while remaining within user-defined safety boundaries. This requires persistent state, recoverable workflows, a reflection loop, and a self-correction loop — not just longer prompts.

### 1.4 Transparent operation
Every decision the system makes — which provider was chosen, which agent was dispatched, which tool was called, what the cost was, what the supervisor's reasoning was — must be observable in real time on the dashboard and replayable after the fact from the audit log. There are no black boxes. The user must be able to pause, inspect, override, or roll back any operation.

### 1.5 Open extensibility
A third-party developer must be able to add a new agent, a new tool, a new LLM provider, a new memory adapter, a new dashboard widget, or a new workflow node — without modifying core code and without rebuilding the runtime. Plugins are loaded at startup, can be hot-reloaded, and are sandboxed by default.

## 2. Design principles

The five principles below are the rules of the road. They are ordered by precedence: when two principles conflict, the earlier one wins.

### 2.1 Modularity over performance
We will accept a 10–20% performance overhead to keep module boundaries clean. A monolithic supervisor that is 20% faster but cannot be extended without a fork is a failure. Concretely: every component communicates via typed interfaces (Pydantic models + Python protocols), every external dependency is injected, and no component imports another component's internals.

### 2.2 Supervision over autonomy
Agents propose; the supervisor disposes. No agent — not even Claude Code, not even the Executive Planner itself — is allowed to take an externally-visible action (writing a file, calling an API, sending a network request, executing a shell command) without the supervisor's commit. The supervisor may delegate commit authority for certain action classes, but the default is "ask first." This is what makes the system safe to run autonomously.

### 2.3 Observability over speed
Every operation emits a structured event on the event bus before and after it executes. Every event is persisted. Every event is replayable. If a feature cannot be made observable, it does not ship. This is non-negotiable because the entire security and audit story depends on it.

### 2.4 Zero-trust over convenience
Every agent runs with the minimum privileges required for its current task. Every tool call is mediated by the permission manager. Every secret is encrypted at rest. Every external request is sandboxed by default. Convenience features (e.g., "trust this agent forever") are opt-in and audited.

### 2.5 Production-readiness over feature count
A smaller feature set that is fully tested, documented, deployable, and operable is strictly better than a larger feature set that is not. We will not merge code that is not tested, not typed, not documented, not observable, and not operable. The roadmap phases exist precisely to enforce this discipline.

## 3. Design invariants

Invariants are properties that must hold at every commit on the main branch. They are checked in CI; a violation blocks merge.

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| INV-01 | Layer dependencies flow inward only (L5 → L1). No L1 import of L2+. | ruff custom rule + import graph test |
| INV-02 | Every external action (file, network, shell, subprocess) goes through a Permission-checked gateway. | Static analysis: grep for `subprocess`, `open`, `requests`, `httpx` outside `core/gateway/` |
| INV-03 | Every component exposes a Pydantic-typed interface. No bare dicts crossing module boundaries. | mypy + custom pytest fixture |
| INV-04 | Every event on the bus is persisted before any side effect is observed. | Integration test on every event-emitting component |
| INV-05 | No secret material in code, configs, logs, or error messages. | gitleaks + secret regex in CI |
| INV-06 | Every agent action can be replayed from the audit log alone. | E2E replay test in Phase 11 |
| INV-07 | The system boots and serves a health check within 5 seconds on the reference hardware. | Boot smoke test in CI |
| INV-08 | The test suite must pass with no network access (mocked providers). | `pytest --offline` run in CI |

## 4. Explicit trade-offs

Every architecture accepts some trade-offs. We accept the following explicitly, and we document them so future contributors do not re-litigate them.

### 4.1 Python over a faster language
We chose Python 3.12 for the runtime despite its slower execution speed, because the LLM ecosystem (OpenAI SDK, Anthropic SDK, MCP SDK, langchain, llama_index, sentence-transformers) is Python-first, and because the bottleneck for an agentic system is LLM latency (seconds), not Python overhead (milliseconds). We accept the GIL constraint by using `asyncio` for I/O-bound work and `ProcessPoolExecutor` for the rare CPU-bound work (embeddings, knowledge-graph reasoning).

### 4.2 Subprocess bridge over in-process agents
We chose to run Claude Code and Hermes as separate subprocesses communicating over JSON-RPC, rather than embedding them in-process. This costs us ~5 ms of latency per call and adds an IPC surface, but it gives us process isolation (a crash in Hermes cannot take down the supervisor), language independence (Claude Code stays as the official CLI, Hermes can be Rust/Go later), and a clean upgrade path (each agent can be versioned and deployed independently).

### 4.3 Event-sourced state over mutable state
The State Manager persists every state transition as an event, and the current state is a fold over the event log. This costs us disk I/O and a small amount of read latency, but it gives us free replay, free audit, free time-travel debugging, and a trivial disaster-recovery story (replay the log).

### 4.4 Strict layering over pragmatic imports
We enforce the L5→L1 dependency direction with a custom ruff rule and an import-graph test. This costs us some boilerplate (dependency injection, interface definitions) and occasionally forces us to push a feature down a layer, but it guarantees that the kernel can be extracted and reused in a completely different product.

### 4.5 Apache 2.0 over copyleft
We chose Apache 2.0 over AGPL or BSL because we want maximum enterprise adoption and because the system's value is in the orchestration layer, not in the individual components. Enterprises will not deploy AGPL software; they will deploy Apache 2.0 software. The explicit patent grant also matters for a system that calls many third-party APIs.

## 5. Deferred decisions

The following are explicitly deferred to post-v1. They are not forgotten; they are scoped out.

- **Multi-tenant SaaS mode.** Requires a control plane, per-tenant encryption keys, and per-tenant rate limits. v1 is single-tenant.
- **Native mobile clients.** The web UI is responsive; native iOS/Android is a v2.
- **Realtime voice mode.** Voice I/O is a plugin; sub-300ms voice conversation is not in v1.
- **Local GPU scheduling.** We rely on Ollama / LM Studio for this.
- **Federated identity (SAML, SCIM).** v1 supports OAuth + API keys. Enterprise SSO is a v1.1.
- **Workflow marketplace.** v1 has a plugin marketplace. Sharing workflows as signed bundles is a v1.1.

## 6. Success criteria for v1

The v1 release is judged against the following concrete criteria. Each must be demonstrable in a public demo and reproducible from the repository:

1. A user can install the system with `docker compose up` and reach the dashboard in under 60 seconds.
2. A user can submit a natural-language goal and watch the supervisor decompose it, dispatch agents, reflect, correct, and deliver a result — all visible on the dashboard.
3. A user can swap the active LLM provider from the dashboard without code changes and without restarting the supervisor.
4. A user can install a plugin from the marketplace without rebuilding the runtime.
5. A user can replay any past task from the audit log.
6. The system passes its full test suite with no network access (all providers mocked).
7. The system has no known Critical or High vulnerabilities in `pip-audit` and `npm audit`.
8. The documentation is sufficient for a new contributor to add a new LLM provider plugin in under two hours.
