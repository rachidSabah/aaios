# ADR-004: Native Integrations Architecture

## Status
Accepted

## Context
The Desktop Runtime requires integration with native OS capabilities and
external tools while maintaining platform independence.

## Decision

### 1. Adapter Pattern for OS APIs
Every native integration (system tray, notifications, credentials, file
watchers) is defined as an abstract interface in `services/desktop/`.
Concrete implementations live in adapter directories or are injected
by the Tauri/Win32 bootstrapper.

### 2. Event Bus for Tool Integration
Integrations with external tools (Git, GitHub, Docker Desktop, WSL, VS Code,
JetBrains IDEs, Claude Code, Codex CLI, Gemini CLI, Ollama) go through the
existing Execution Engine Framework. Each tool gets an execution domain with
well-defined actions and parameters.

### 3. System Tray as a Service
The `SystemTray` service manages tray icon, tooltip, and context menu. It
publishes tray events on the Event Bus. The concrete tray implementation
(Tauri system tray, native Win32) is injected at boot.

### 4. Notification Routing
Desktop notifications flow through the `NativeNotificationService`, which
publishes them on the Event Bus. Both the system tray and the Mission Control
dashboard subscribe to display notifications. OS-level toasts are handled by
the platform adapter.

## Consequences
- All native integrations are testable at the interface level
- Adding a new platform requires only adapter implementations
- External tools integrate without direct coupling
- Notifications are visible through multiple surfaces simultaneously
