# ADR-001: Desktop Runtime Architecture

## Status
Accepted

## Context
AgenticOS requires a native desktop application capable of operating completely
offline while preserving every existing capability. The architecture must remain
platform-neutral to support Windows (primary), Linux, and macOS via adapter
implementations.

## Decision

### 1. Desktop Runtime is a First-Class Platform Service
The Desktop Runtime joins the existing platform services (EventBus, Execution
Engine, Security Framework, Memory Framework, Provider Framework) as a
first-class subsystem. It owns the desktop application lifecycle.

### 2. Adapter-Based Platform Abstraction
All OS-specific operations (system tray, notifications, credentials, process
management) go through adapter abstractions defined in `services/desktop/`.
Concrete implementations for Tauri/Win32 are injected at boot.

### 3. Service Hierarchy
A single `DesktopRuntimeManager` orchestrates a dependency-ordered service
graph. Each service implements a well-defined interface; the manager handles
boot order, health monitoring, and graceful shutdown.

### 4. Event-Driven Integration
All desktop services publish lifecycle events (desktop.*) on the existing Event
Bus. The Mission Control dashboard, system tray, and external plugins subscribe
to these events rather than polling.

### 5. No Architecture Bypass
Desktop services integrate exclusively through existing public ports:
- Event Bus for pub/sub
- Platform Adapter for OS calls
- Gateway for subprocess/shell
- Provider Framework for update providers

### 6. Provider-Based Update Framework
The update system is provider-agnostic. GitHub Releases is the first
implementation. Custom providers (enterprise CDN, local file share, S3)
require only a new `UpdateProvider` implementation — no kernel changes.

## Consequences
- Windows support works out of the box
- Linux/macOS require only adapter class implementations
- No breaking changes to existing services
- All existing tests continue to pass
- Desktop Runtime adds 22 REST API endpoints
