# 01 — Goals & Design Principles

> **Audience:** implementers and reviewers.
> **Purpose:** pin down the non-negotiable design invariants before any code is written, so that every later trade-off can be evaluated against them.

---

## 1. Primary goals

The system exists to achieve six concrete outcomes. Every architectural decision must be traceable to at least one of them.

### 1.1 Generic agent orchestration
The system must orchestrate **capabilities**, not products. A future agent — OpenHands, Cline, Roo Code, Gemini CLI, Codex CLI, any custom agent, any MCP-backed agent — must be addable by implementing the `GenericAgent` interface and registering with the Agent Registry. No core code may change. The Supervisor asks the registry *"which agents can handle capability X?"* and chooses based on health, load, cost, and track record — never by name.

### 1.2 Poly-model routing
The user must never be locked into a single LLM provider. The system supports at least 13 providers (OpenAI, Anthropic, Google, OpenRouter, DeepSeek, GLM, NVIDIA, Ollama, LM Studio, Azure OpenAI, Mistral, Groq, Custom) and allows per-task routing, automatic failover, and side-by-side cost comparison. **Agents never call providers directly — every LLM call goes through the centralized Model Router.** A provider going down, deprecating a model, or changing its pricing must never require a code change in any agent.

### 1.3 Long-horizon autonomy with reliable execution
The system must execute multi-step, multi-hour tasks without human intervention, while remaining within user-defined safety boundaries. This requires persistent state, a Task Orchestrator with checkpointing/resume/cancellation, an event-sourced State Manager, a Reflection loop, and a Self-Correction loop — not just longer prompts.

### 1.4 Transparent operation
Every decision the system makes — which capability was required, which agents were candidates, which was selected and why, which provider was chosen, which tool was called, what the cost was, what the supervisor's reasoning was — must be observable in real time on the dashboard and replayable after the fact from the audit log. There are no black boxes. The user can pause, inspect, override, or roll back any operation to any prior checkpoint.

### 1.5 Open extensibility
A third-party developer must be able to add a new agent, a new tool, a new LLM provider, a new memory adapter, a new dashboard widget, or a new workflow node — without modifying core code and without rebuilding the runtime. Plugins are loaded at startup, can be hot-reloaded, and are sandboxed by default. The Agent SDK scaffolds a new agent plugin in one command.

### 1.6 Windows-first production readiness
The system is built and tested on Windows 11 first. It runs as native Windows Services, uses Task Scheduler for persistence, PowerShell for shell operations, and Windows-native sandboxing (Job Objects, AppContainer, WDAC). Linux compatibility is achieved via an abstraction layer and is a v1.1 goal — not a v1 deliverable, but never an afterthought.

## 2. Design principles

The six principles below are the rules of the road. They are ordered by precedence: when two principles conflict, the earlier one wins.

### 2.1 Genericism over convenience
The system orchestrates capabilities, not products. No code outside `agents/_impls/<name>/` may reference a specific agent implementation by name. The Supervisor, Task Orchestrator, Capability Selector, Memory, Security, and Dashboard are all implementation-agnostic. This is enforced by a CI regex ban on agent product names in core directories. If a feature "requires" naming a specific agent, the feature is wrong — refactor it.

### 2.2 Modularity over performance
We will accept a 10–20% performance overhead to keep module boundaries clean. Every component communicates via typed interfaces (Pydantic models + Python protocols), every external dependency is injected, and no component imports another component's internals. The five-layer architecture (L1 Kernel → L5 Surfaces) is enforced by ruff.

### 2.3 Supervision over autonomy
Agents propose; the supervisor disposes. No agent — not even the Supervisor itself — is allowed to take an externally-visible action (writing a file, calling an API, sending a network request, executing a shell command) without the supervisor's commit. The supervisor may delegate commit authority for certain action classes via approval gates, but the default is "ask first."

### 2.4 Observability over speed
Every operation emits a structured event on the event bus before and after it executes. Every event is persisted. Every event is replayable. If a feature cannot be made observable, it does not ship. The entire security and audit story depends on this.

### 2.5 Zero-trust over convenience
Every agent runs with the minimum privileges required for its current task. Every tool call is mediated by the Permission Manager. Every secret is encrypted at rest and rotatable. Every external request is sandboxed by default. Convenience features (e.g., "trust this agent forever") are opt-in, audited, and reviewed by the least-privilege analyzer.

### 2.6 Windows-first over cross-platform shortcuts
We build for Windows 11 first, using Windows-native primitives (Services, Task Scheduler, Job Objects, PowerShell, WDAC). We do not require WSL2 or Docker for the primary deployment. Linux compatibility is achieved through an explicit abstraction layer (`core/platform/windows.py` and `core/platform/linux.py`), not through `if sys.platform ==` checks scattered through the codebase. The Linux adapters are stubbed in v1 and completed in v1.1.

## 3. Design invariants

Invariants are properties that must hold at every commit on the main branch. They are checked in CI; a violation blocks merge.

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| INV-01 | Layer dependencies flow inward only (L5 → L1). | ruff custom rule + import graph test |
| INV-02 | Every external action (file, network, shell, subprocess) goes through the Gateway. | Static analysis: regex ban on `subprocess`, `open`, `requests`, `httpx`, `socket` outside `core/gateway/` |
| INV-03 | Every component exposes a Pydantic-typed interface. No bare dicts crossing module boundaries. | mypy + custom pytest fixture |
| INV-04 | Every event on the bus is persisted before any side effect is observed. | Integration test on every event-emitting component |
| INV-05 | No secret material in code, configs, logs, or error messages. | gitleaks + secret regex in CI |
| INV-06 | Every agent action can be replayed from the audit log alone. | E2E replay test in Phase 13 |
| INV-07 | The system boots and serves a health check within 5 seconds on the reference hardware. | Boot smoke test in CI (Windows) |
| INV-08 | The test suite must pass with no network access (mocked providers). | `pytest --offline` run in CI |
| INV-09 | No code outside `agents/_impls/<name>/` references a specific agent implementation by name. | CI regex ban on `claude`, `hermes`, `openhands`, `cline`, `roo`, `gemini`, `codex` in `core/`, `services/`, `supervisor/`, `orchestrator/`, `surfaces/` |
| INV-10 | Every `GenericAgent` implementation satisfies the 11-method interface. | mypy Protocol check + interface test suite |
| INV-11 | All Windows Services run with auto-restart configured (3 retries, then fail). | `aaios doctor` checks `sc qfailure` |
| INV-12 | All tests pass on `windows-latest` AND `ubuntu-latest` (Linux may skip Windows-only features). | CI matrix |

## 4. Explicit trade-offs

Every architecture accepts trade-offs. We accept the following explicitly.

### 4.1 Python over a faster language
We chose Python 3.12 for the runtime despite its slower execution speed, because the LLM ecosystem (OpenAI SDK, Anthropic SDK, MCP SDK, langchain, llama_index, sentence-transformers) is Python-first, and because the bottleneck for an agentic system is LLM latency (seconds), not Python overhead (milliseconds). Python 3.12 has first-class Windows support.

### 4.2 Subprocess bridge over in-process agents
We run CodingAgents and DesktopAgents as subprocesses communicating over JSON-RPC. This costs ~5 ms of latency per call but gives us: process isolation (a crash in an agent cannot take down the supervisor), language independence (future agents can be Rust/Go/Node), independent versioning, and a clean upgrade path. On Windows, subprocesses are managed via CreateProcess + Job Objects.

### 4.3 Event-sourced state over mutable state
The State Manager persists every state transition as an event; current state is a fold over the event log. This costs disk I/O but gives free replay, free audit, free time-travel debugging, and trivial disaster recovery.

### 4.4 Strict layering over pragmatic imports
We enforce L5→L1 dependency direction with ruff and an import-graph test. This costs boilerplate but guarantees the kernel can be extracted and reused.

### 4.5 Capability-based selection over name-based dispatch
The Capability Selector scores multiple candidate agents per step instead of hardcoding "use Claude Code for code." This costs runtime (scoring) but makes the system future-proof: a new agent is competitive the moment it registers.

### 4.6 Windows-first over cross-platform parity
We build for Windows first using native primitives, with Linux as an abstraction-layer concern. This means Linux support ships later (v1.1) but Windows support is excellent from day one — no WSL2 dependency, no Docker requirement, native services and scheduling.

### 4.7 Apache 2.0 over copyleft
Maximum enterprise adoption, explicit patent grant. The system's value is in the orchestration layer, not in any individual component.

## 5. Deferred decisions

- **Multi-tenant SaaS mode.** Requires a control plane, per-tenant encryption keys, per-tenant rate limits. v1 is single-tenant.
- **Linux as primary target.** Linux is a v1.1 goal. Architecture is ready; adapters are stubbed.
- **Native mobile clients.** Responsive web only.
- **Realtime voice mode.** Voice Agent interface exists; sub-300ms voice conversation is post-v1.
- **Local GPU scheduling.** We rely on Ollama / LM Studio.
- **Federated identity (SAML, SCIM).** OAuth + API keys in v1; enterprise SSO is v1.1.
- **Workflow marketplace.** Plugin marketplace in v1; signed workflow bundles are v1.1.
- **TPM 2.0 / hardware root of trust.** Master key is software-derived in v1; TPM integration is a v1.1 stretch.

## 6. Success criteria for v1

The v1 release is judged against the following concrete criteria, each demonstrable in a public demo and reproducible from the repository:

1. A Windows 11 user can install the system via the `.exe` installer and reach the dashboard in under 5 minutes.
2. A user can submit a natural-language goal and watch the supervisor decompose it, dispatch agents (selected by capability, not name), reflect, correct, and deliver a result — all visible on the dashboard.
3. A user can swap the active LLM provider from the dashboard without code changes and without restarting the supervisor.
4. A user can install a new CodingAgent plugin (e.g., OpenHands) from the marketplace, and the next coding task may be dispatched to it — without rebuilding the runtime or restarting the supervisor.
5. A user can replay any past task from the audit log alone.
6. The system passes its full test suite with no network access (all providers mocked).
7. The system has no known Critical or High vulnerabilities in `pip-audit` and `npm audit`.
8. The documentation is sufficient for a new contributor to add a new LLM provider plugin in under two hours.
9. `aaios doctor` passes with no warnings on a clean Windows 11 install.
10. All CI checks pass on both `windows-latest` and `ubuntu-latest` runners.
