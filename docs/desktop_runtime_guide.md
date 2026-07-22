# Desktop Runtime Guide

> Version 1.0.0-rc1 — Phase 4, Milestone 6

## Overview

The Desktop Runtime transforms AgenticOS into a production-quality native
desktop application capable of operating completely offline while preserving
every capability already implemented.

### Architecture

```
┌──────────────────────────────────────────────────┐
│              DESKTOP RUNTIME MANAGER              │
│  ├── DiagnosticsManager   ├── LocalDatabaseManager │
│  ├── NativeCredentialStore ├── WindowManager       │
│  ├── WorkspaceManager     ├── SystemTray          │
│  ├── NativeNotificationService ├── OfflineRuntime │
│  ├── LocalAIRuntimeManager ├── PerfMonitor        │
│  ├── DesktopPluginLoader  ├── DesktopUpdater      │
│  └── BackgroundServiceRunner └── CrashReporter    │
├──────────────────────────────────────────────────┤
│              API LAYER (FastAPI)                  │
│  22 Desktop REST API endpoints                   │
├──────────────────────────────────────────────────┤
│              TAURI RUNTIME (Desktop Shell)        │
│  Windows MSI/EXE — Linux/macOS via adapters      │
└──────────────────────────────────────────────────┘
```

## Key Subsystems

### Desktop Runtime Manager (`services/desktop/manager.py`)
Central lifecycle orchestrator that boots all desktop services in dependency
order:

1. DiagnosticsManager — captures startup crashes
2. NativeCredentialStore — OS credential manager
3. LocalDatabaseManager — embedded SQLite database
4. WindowManager — window state tracking
5. WorkspaceManager — workspace persistence
6. SystemTray — tray icon and menu
7. NativeNotificationService — desktop notifications
8. OfflineRuntimeManager — connectivity monitoring
9. LocalAIRuntimeManager — local inference engines
10. PerformanceMonitor — real system metrics
11. DesktopPluginLoader — hot-reload plugins
12. DesktopUpdater — auto-update integration
13. BackgroundServiceRunner — periodic tasks
14. CrashReporter — exception capture

### Offline Runtime Manager (`services/desktop/offline.py`)
- Monitors connectivity via periodic HTTP probes
- Queues outgoing operations when offline
- Flushes the queue when connectivity returns
- Publishes `desktop.offline` / `desktop.online` events
- Persists the sync queue to disk

### Local AI Runtime Manager (`services/desktop/local_ai.py`)
- Discovers installed local AI engines (Ollama, llama.cpp, LocalAI)
- Probes for running instances via HTTP health checks
- Publishes `desktop.local_ai.engines_found` events
- Registers engines through the existing Execution Engine Framework

### Desktop Updater (`services/desktop/updater.py`)
- Bridges the provider-based Update Framework to the desktop UI
- Registers GitHubReleaseProvider with the UpdateManager
- Exposes `check()` / `install()` workflows
- Integrates with BackgroundUpdateService
- Publishes `desktop.update.*` events

### Provider-based Update Framework
- **UpdateManager** — orchestrates check/download/verify/install/rollback
- **UpdateProvider** — abstract contract (GitHub-agnostic)
- **GitHubReleaseProvider** — first concrete implementation
- **ReleaseChannelManager** — per-channel auto/notify/off policies
- **PackageVerifier** — SHA-256 integrity + pluggable signature verification
- **RollbackManager** — wraps BackupManager/RecoveryManager
- **BackgroundUpdateService** — configurable periodic checks
- **ManifestGenerator** — offline/enterprise manifest serialization
- **VersionManager** — semver parsing, channel-aware upgrade rules

## REST API

The Desktop Runtime exposes 22 REST API endpoints under `/api/v1/desktop/`:

| Endpoint | Description |
|----------|-------------|
| `GET /status` | Desktop Runtime boot status |
| `GET /diagnostics` | Run all diagnostic checks |
| `GET /perfmon` | Current performance metrics |
| `GET /perfmon/history` | Performance metric history |
| `GET /offline` | Offline mode status |
| `GET /local-ai` | Local AI engine status |
| `GET /notifications` | Recent desktop notifications |
| `GET /windows` | Open window states |
| `GET /workspaces` | Workspace information |
| `GET /plugins` | Installed desktop plugins |
| `GET /logs` | Recent log entries |
| `GET /updates` | Update status |
| `POST /updates/check` | Check for updates |
| `GET /credentials` | List credential keys |
| `GET /system` | System information |
| `GET /services` | List desktop services |

## Offline Capabilities

- **Offline authentication** via local credential store
- **Offline memory** via local database
- **Offline MCP** through cached provider manifests
- **Offline execution** through execution engine framework
- **Offline workflows** through cached work plans
- **Offline Mission Control** through Desktop Runtime dashboard
- **Offline documentation** cached locally
- **Offline plugin execution** through plugin loader
- **Local synchronization queue** for deferred operations

## Update Framework

### Channels
- **STABLE** — production releases, auto-check + auto-install
- **LTS** — long-term support (opt-in)
- **BETA** — pre-release candidates (notify only)
- **NIGHTLY** — nightly builds (notify only)
- **ENTERPRISE** — enterprise releases (opt-in)

### Update Pipeline
1. Provider fetches manifest from GitHub Releases
2. VersionManager checks channel policy
3. Downloader streams package + computes SHA-256
4. PackageVerifier checks integrity + signature
5. RollbackManager creates pre-update checkpoint
6. Migration runs (database, config, plugins)
7. ReleaseValidator validates the installation
8. On failure: automatic rollback to checkpoint

## Packaging

### Windows
- **MSI** — Windows Installer package
- **EXE** — Self-contained installer
- **Portable ZIP** — No-install portable version

### Future (adapter architecture)
- AppImage (Linux)
- DEB (Debian/Ubuntu)
- RPM (Fedora/RHEL)
- DMG (macOS)
- PKG (macOS)

## Security

- **Native Credential Storage** — Windows Credential Manager
- **Encrypted Local Secrets** — AES-encrypted file store fallback
- **Workspace Isolation** — sandboxed plugin execution
- **Secure IPC** — through FastAPI with CORS policies
- **Plugin Sandboxing** — per-plugin sandbox enable/disable
- **Audit Logging** — hash-chained audit entries
- **Signature Verification** — digital signature verification for packages

## Testing

| Category | Status |
|----------|--------|
| Unit Tests | ✅ Implemented |
| Integration Tests | ✅ Implemented |
| Desktop UI Tests | ✅ Implemented |
| Native Integration Tests | ✅ Implemented |
| Offline Tests | ✅ Implemented |
| Update Tests | ✅ Implemented |
| Rollback Tests | ✅ Implemented |
| Performance Tests | ✅ Implemented |
