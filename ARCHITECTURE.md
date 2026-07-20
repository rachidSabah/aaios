# AAiOS Core Architecture
## Version 1.0.0-rc1 — Desktop Runtime Architecture

This document outlines the core architectural components of AAiOS.

---

### 1. Decoupled Modular Layers

```
┌──────────────────────────────────────────────────────┐
│                      SURFACES                         │
│   CLI (Typer)    Web UI (Next.js)    Desktop App     │
│                      Desktop API (FastAPI)            │
└──────────────────────────┬───────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────┐
│                     SERVICES                          │
│  Desktop Runtime  •  Update Framework  •  Backup      │
│  Diagnostics  •  Crash Reporter  •  Performance      │
│  Offline Mode  •  Local AI  •  Plugin Loader        │
│  Credential Store  •  Notifications  •  System Tray  │
│  Agent Registry  •  Model Router  •  Memory          │
│  Execution Engine  •  Security  •  Knowledge         │
│  Engineering Intelligence  •  Research               │
│  Installer  •  Validator  •  Self-Healing            │
└──────────────────────────┬───────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────┐
│                       CORE                             │
│  Bootstrap • Config • Event Bus • Platform Adapter    │
│  Gateway (FS, Shell, Net) • State Manager • DI        │
│  Contracts (Actor, Event, Health, Permission, etc.)   │
└──────────────────────────────────────────────────────┘
```

### 2. Dependency Invariants

*   Core modules MUST NOT import from surfaces or services.
*   Surface CLI/API tools communicate with services strictly via standardized API parameters.
*   Desktop Runtime integrates through existing public ports (Event Bus, Platform Adapter, Gateway, Provider Framework).
*   No subsystem may bypass the established architecture.

### 3. Desktop Runtime Services

| Service | Description | Event Topics |
|---------|-------------|--------------|
| DesktopRuntimeManager | Lifecycle orchestrator | `desktop.booted`, `desktop.shutting_down` |
| WindowManager | Multi-window state tracking | `desktop.window.*` |
| WorkspaceManager | Workspace persistence | `desktop.workspace.*` |
| NativeNotificationService | Desktop notifications | `desktop.notification` |
| SystemTray | System tray icon + menu | `desktop.tray.*` |
| OfflineRuntimeManager | Connectivity monitoring | `desktop.offline`, `desktop.online` |
| LocalAIRuntimeManager | Local AI engine management | `desktop.local_ai.*` |
| PerformanceMonitor | System resource metrics | `desktop.perfmon.*` |
| DiagnosticsManager | Health check execution | `desktop.diagnostics.*` |
| CrashReporter | Exception capture | `desktop.crash.*` |
| DesktopPluginLoader | Plugin installation | `desktop.plugin.*` |
| DesktopUpdater | Auto-update integration | `desktop.update.*` |
| BackgroundServiceRunner | Periodic task execution | `desktop.background.*` |
| NativeCredentialStore | OS credential management | — |
| LocalDatabaseManager | Embedded SQLite database | — |

### 4. Update Framework Architecture

```
UpdateProvider (ABC)
  └── GitHubReleaseProvider  (first implementation)
  └── CustomProvider         (future — no kernel changes)

UpdateManager
  ├── ReleaseChannelManager  (channel policy)
  ├── VersionManager         (semver + channel rules)
  ├── download_asset()       (streaming + SHA-256)
  ├── PackageVerifier        (integrity + signature)
  └── RollbackManager        (wraps BackupManager)

BackgroundUpdateService      (periodic checks)
```

### 5. Platform Support Matrix

| Platform | Desktop Adapter | Packaging | Status |
|----------|---------------|-----------|--------|
| Windows 11 | Tauri 2 + Win32 | MSI, EXE, ZIP | ✅ Supported |
| Windows Server 2022 | Tauri 2 + Win32 | MSI, EXE, ZIP | ✅ Supported |
| Ubuntu 24.04 / Debian 12 | Adapter stub | AppImage, DEB | 🔄 Phase 1.1 |
| Fedora 40 / RHEL 9 | Adapter stub | RPM | 🔄 Phase 1.1 |
| macOS 14+ | Adapter stub | DMG, PKG | 🔄 Phase 1.2 |
