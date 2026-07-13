# 06 — Technology Stack

> **Audience:** all stakeholders.
> **Purpose:** the locked technology choices, with the rationale and the rejected alternatives. **Windows 11 is the primary target; Linux is a v1.1 goal.**

---

## 1. Locked stack

| Layer | Component | Technology | Version |
|-------|-----------|-----------|---------|
| **Backend runtime** | Language | Python | 3.12+ (Windows native installer / winget) |
| | Async runtime | asyncio + uvloop (uvloop Linux-only; Windows uses default asyncio) | stdlib + 0.19+ |
| | HTTP framework | FastAPI | 0.115+ |
| | ASGI server | Uvicorn (workers=1) | 0.32+ |
| | Validation | Pydantic | v2 |
| | ORM | SQLAlchemy | 2.x (async) |
| | Migrations | Alembic | 1.13+ |
| | CLI | Typer + Rich | 0.12+ / 13.7+ |
| | DI | `dependency-injector` | 4.41+ |
| | Templating | Jinja2 | 3.1+ |
| | Testing | pytest + pytest-asyncio + hypothesis | 8.x / 0.23+ / 6.x |
| | Static analysis | ruff + mypy + bandit | 0.6+ / 1.11+ / 1.7+ |
| | Secret scanning | gitleaks | 8.18+ |
| | Windows service | NSSM (Non-Sucking Service Manager) + pywin32 | NSSM 2.24+ / pywin32 306+ |
| | Windows shell | PowerShell 7+ (preferred), cmd.exe (fallback) | 7.4+ |
| | Windows scheduling | Windows Task Scheduler (via `schtasks` / COM API) | built-in |
| | Windows packaging | PyInstaller + Inno Setup | 6.x / 6.x |
| **Frontend** | Framework | Next.js | 16 (App Router, RSC) |
| | UI library | React | 19 |
| | Styling | Tailwind CSS | 4 |
| | Component system | shadcn/ui | latest |
| | State | Zustand + TanStack Query | 4.x / 5.x |
| | Forms | react-hook-form + zod | 7.x / 3.x |
| | Charts | Recharts | 2.x |
| | WebSockets | native + socket.io-client | — |
| | Testing | Vitest + Playwright | 1.6+ / 1.45+ |
| **Desktop shell** | Native wrapper | Tauri | 2.x (WebView2 on Windows) |
| | Desktop automation | PyAutoGUI + Pywinauto + Playwright | 0.9+ / 0.6+ / 1.45+ |
| | OCR | Tesseract (Windows installer) | 5.4+ |
| **Data layer** | Relational DB (prod) | PostgreSQL 16 (Windows native installer) | 16 |
| | Relational DB (dev/test) | SQLite (Windows-native) | 3.45+ |
| | Vector DB | Qdrant (Windows binary) | 1.10+ |
| | Knowledge graph (default) | NetworkX (in-process) | 3.3+ |
| | Knowledge graph (optional) | Neo4j Community Edition (Windows installer) | 5.x |
| | Cache / pub-sub | Redis on Windows via Memurai (or skip in single-machine mode) | Memurai 4.x / Redis 7 |
| | Embeddings | OpenAI / local sentence-transformers | — |
| **Agent runtimes** | CodingAgent (default impl) | Claude Code (`claude` CLI on Windows) | latest |
| | DesktopAgent (default impl) | Hermes (in-house daemon: Python + PyAutoGUI + Playwright + Pywinauto) | 0.1 |
| | Subprocess binding | Windows CreateProcess + Job Objects (via `subprocess` + `pywin32`) | stdlib |
| **Containerization (OPTIONAL)** | Container runtime | Docker Desktop on Windows (WSL2 backend) | 4.30+ |
| | Orchestration | Docker Compose v2 | 2.20+ |
| | Images | python:3.12-slim, node:22-alpine, postgres:16, qdrant/qdrant | — |
| **CI/CD** | GitHub Actions | hosted runners (windows-latest for Windows tests, ubuntu-latest for Linux tests) | — |
| | Release | semantic-release + auto-changelog | — |
| **Observability** | Telemetry | OpenTelemetry SDK + OTLP exporter | 1.25+ |
| | Logs | structlog → JSON | 24.x |
| | Metrics scraping | Prometheus (Windows binary) — optional | 2.50+ |
| **Security** | Auth | OAuth2 (Authlib) + API keys | — |
| | Authorization | in-house policy engine (Python rules, Cedar-style syntax) | — |
| | Secret encryption | `cryptography.fernet` (AES-128-CBC + HMAC) | — |
| | Windows sandboxing | Job Objects + AppContainer + WDAC policies | built-in |
| | Plugin sandboxing | restricted Python `__builtins__` + Job Objects | — |
| | Antivirus integration | Windows Defender (exclusions for AAiOS dirs, on-access scan for plugin downloads) | built-in |

## 2. Windows-first — what it means concretely

### 2.1 Windows is the primary target
Windows 11 is the OS the system is built and tested on first. Every CI run includes a `windows-latest` job that must pass. Linux is supported via the same abstraction layer, but Linux-specific paths are stubbed in v1 and completed in v1.1.

### 2.2 Native binaries preferred
We prefer native Windows binaries over Docker containers:
- **PostgreSQL 16** has a native Windows installer (EnterpriseDB). Used directly.
- **Qdrant** ships a Windows binary. Used directly.
- **Redis** does not officially support Windows. Options: (a) Memurai (Redis-compatible, Windows-native, free for dev/small prod), (b) skip Redis entirely in single-machine mode (the in-process event bus + SQLite is enough for v1 single-tenant), (c) Redis on WSL2 (heavier). v1 default: **skip Redis** in single-machine mode; add via Docker/Memurai when multi-process is needed.
- **Python 3.12** native Windows installer from python.org. Bundled in the desktop installer via PyInstaller.
- **Node 22** native Windows installer. Bundled in the desktop installer for the Next.js build (or pre-built and shipped as static files).
- **Tesseract OCR** Windows installer.
- **Tauri** uses WebView2 (pre-installed on Windows 11).

### 2.3 PowerShell first
- The Gateway's `shell.exec` defaults to PowerShell 7+.
- All shell scripts in the repo are `.ps1` first, `.sh` second (Linux compat in v1.1).
- The CLI's `aaios doctor` command runs PowerShell probes (service status, port checks, disk space via `Get-PSDrive`, etc.).
- The `aaios service install` command uses `New-Service` (or NSSM) to install AAiOS as a Windows Service.

### 2.4 Windows Services for background processes
The Supervisor, API server, and worker pool run as Windows Services:
- Installed via NSSM (`nssm install aaios-runtime …`) or `pywin32`'s `win32serviceutil`.
- Run as a dedicated local service account (`NT SERVICE\AAiOS` or a user-created `.\AAiOS` account) with minimal privileges.
- Auto-restart on failure (configured via `sc failure`).
- Logs to Windows Event Log + structured JSON files.

### 2.5 Task Scheduler for scheduled jobs
The Orchestrator's scheduler delegates to Windows Task Scheduler for persistence across reboots:
- Recurring tasks → `schtasks /create /sc DAILY /st 09:00 …` (or via the COM API for richer triggers).
- One-shot delayed tasks → `schtasks /create /sc ONCE …`.
- The Orchestrator keeps an in-process schedule cache for fast lookup, and syncs to Task Scheduler for durability.

### 2.6 Windows paths
- Install dir: `C:\Program Files\AAiOS\` ( binaries).
- Config dir: `%ProgramData%\AAiOS\config\` (system-wide config, readable by service account).
- Data dir: `%ProgramData%\AAiOS\data\` (Postgres, Qdrant, audit log, runtime scratch).
- User data dir: `%APPDATA%\AAiOS\` (per-user memory scopes, preferences).
- Logs dir: `%ProgramData%\AAiOS\logs\`.
- Temp dir: `%TEMP%\AAiOS\` (per-user temp, cleaned on service start).

The Gateway's `fs` sub-gateway normalizes paths (handles `/` vs `\`, long-path prefix `\\?\`, UNC paths) so agents see consistent OS-native paths.

### 2.7 Windows sandboxing (no seccomp, no bubblewrap)
- **Subprocess sandboxing:** Windows Job Objects enforce CPU/memory limits and child-process grouping. AppContainer provides a low-privilege execution environment. Windows Defender Application Control (WDAC) policies can restrict which binaries an agent subprocess may invoke.
- **Plugin sandboxing:** restricted Python `__builtins__` (same as Linux) + Job Objects for the plugin worker process. No filesystem or network access except via the Gateway.
- **No `bwrap`, no `seccomp`.** These are Linux-only. The Windows sandboxing stack is Job Objects + AppContainer + WDAC.
- See `07-security-model.md` for the full sandboxing model.

### 2.8 Docker is optional
Docker Desktop on Windows (via WSL2) is supported as an alternative deployment mode — useful for users who already have Docker set up, or for Linux-machine deployment. The `docker-compose.yml` (Phase 12) is the secondary deployment path. The primary path is the native Windows installer + Windows Services.

## 3. Rationale per layer

### 3.1 Backend — Python 3.12 (unchanged)
The LLM ecosystem is Python-first (MCP SDK, OpenAI/Anthropic/Google/Mistral/DeepSeek SDKs, sentence-transformers, langchain). Python 3.12 has a native Windows installer and first-class Windows support. `uvloop` is Linux-only; on Windows we use the default asyncio event loop, which is fast enough for our I/O-bound workload.

### 3.2 Frontend — Next.js 16 + React 19 (unchanged)
App Router + RSC give us the data-heavy dashboard / interactive-widget split we need. Tailwind 4 + shadcn/ui give us accessible, themeable components. Next.js builds to static files that the Tauri desktop shell can serve, and to a Node server that the API host can serve.

### 3.3 Vector DB — Qdrant (unchanged)
Qdrant ships a native Windows binary. Rust core, fast, excellent filtering (needed for memory scoping). Hybrid search (dense + sparse) supported.

### 3.4 Relational DB — PostgreSQL 16 (prod) + SQLite (dev/test) (unchanged)
Postgres 16 has a Windows installer. SQLite is Windows-native. SQLAlchemy 2 async hides the difference. The event-sourced state manager uses JSONB on Postgres and TEXT on SQLite.

### 3.5 Agent binding — subprocess + JSON-RPC, Windows CreateProcess (refined)
Same architecture as before; the implementation uses Windows-specific subprocess management:
- `subprocess.Popen` with `creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` for headless agents.
- Job Objects (`pywin32`'s `win32job`) for resource limits and child-process grouping (so cancelling a Hermes task kills its child browser processes).
- Named pipes or stdin/stdout for JSON-RPC (named pipes have lower latency on Windows; stdin/stdout is simpler and cross-platform — we use stdin/stdout for portability).

### 3.6 License — Apache 2.0 (unchanged)
Maximum enterprise adoption, explicit patent grant, compatible with virtually all other open-source licenses.

### 3.7 Deployment — Windows Services + Task Scheduler native, Docker optional (changed)
The primary deployment is native Windows: install via Inno Setup installer, register as Windows Services, schedule via Task Scheduler. The Docker Compose deployment is the secondary path for users who prefer containers or who deploy to Linux. See `08-deployment-topology.md` for the full topology.

## 4. Rejected alternatives (Windows-first specific)

### 4.1 Linux-first with Docker-only
**Rejected because:** the user explicitly required Windows-first. The native Windows deployment is also a better story for enterprise desktop deployment (no Docker Desktop license issues, no WSL2 complexity for end users).

### 4.2 .NET / C# for the backend
**Rejected because:** the LLM ecosystem is Python-first. Rewriting all the SDKs in C# would be a multi-year effort. Python on Windows is fast enough and well-supported.

### 4.3 Electron for the desktop shell
**Rejected because:** Tauri is smaller, faster, and uses WebView2 (pre-installed on Windows 11) instead of bundling Chromium. Memory footprint is ~10× smaller.

### 4.4 WSL2-only deployment
**Rejected because:** it forces every user to enable WSL2, install a Linux distro, and learn Linux file paths. The Windows-native path is simpler for the target audience. WSL2 remains an option for power users.

### 4.5 Memcached instead of Redis
**Rejected because:** we need pub/sub, not just cache. Memcached has no pub/sub. In single-machine mode we skip the cache entirely (in-process state is enough); when we need it, Memurai (Redis-compatible, Windows-native) is the choice.

## 5. Compatibility and versioning

- **Windows:** Windows 11 (10.0.22000+) required for v1. Windows 10 LTSC 2021 supported on a best-effort basis. Windows Server 2022 supported for server deployments.
- **Python:** 3.12 minimum, native Windows installer.
- **Node:** 22 LTS, native Windows installer.
- **Postgres:** 16 minimum (native Windows installer from EnterpriseDB).
- **Qdrant:** 1.10+ (Windows binary from Qdrant releases).
- **PowerShell:** 7.4+ (installed by the AAiOS installer if not present).
- **WebView2:** pre-installed on Windows 11; bundled by the Tauri installer as a fallback.

## 6. Dependency policy (unchanged)

- All third-party Python deps pinned in `pyproject.toml` with `~=` and hashed in `requirements.lock`.
- All npm deps pinned in `package.json` with `^` and locked in `pnpm-lock.yaml`.
- Renovate bot opens PRs for outdated deps. Major bumps require manual review.
- Any dep with an unpatched Critical CVE is auto-replaced within 7 days.
- Any dep that doesn't ship Windows wheels is flagged — we don't accept source-only distributions on Windows.

## 7. Build artifacts

| Artifact | Where | Produced by |
|----------|-------|-------------|
| Windows installer (`.exe`) | `dist/AAiOS-Setup-x.y.z.exe` | Inno Setup + PyInstaller |
| Python wheel | `dist/aaios-*.whl` | `hatch build` |
| Docker images (optional) | `ghcr.io/rachidsabah/aaios-{runtime,web,hermes,worker}` | GitHub Actions |
| CLI binary (standalone) | `dist/aaios.exe` | PyInstaller |
| Documentation site | `https://aaios.dev` (deferred) | MkDocs Material |

## 8. Linux compatibility path (v1.1)

The codebase is structured so that Linux support is additive, not a rewrite:
- The `core/gateway/` has Windows and Linux adapters (selected at boot via `sys.platform`).
- The `core/scheduler/` has a Windows Task Scheduler adapter and an APScheduler adapter.
- The `core/service_manager/` has a Windows Service adapter (NSSM/pywin32) and a systemd adapter.
- The `deploy/` directory has `windows/` and `linux/` subdirectories with platform-specific scripts.

v1 ships the Windows adapters complete and the Linux adapters stubbed (raising `NotImplementedError` with a clear message). v1.1 completes the Linux adapters. No core code changes between v1 and v1.1 for Linux support — only adapter implementations.

This concludes the tech stack document. For the security implications, see [`07-security-model.md`](07-security-model.md).
