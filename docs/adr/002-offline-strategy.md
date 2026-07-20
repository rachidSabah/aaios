# ADR-002: Offline Strategy

## Status
Accepted

## Context
The Desktop Runtime must support full offline operation:
- Offline authentication, memory, MCP, execution, workflows
- Offline Mission Control and documentation
- Offline plugin execution
- Automatic synchronization when connectivity returns

## Decision

### 1. Connectivity Probes
A dedicated `OfflineRuntimeManager` probes connectivity against multiple URLs
at a configurable interval (default 30s). Online/offline transitions are
published as events on the Event Bus.

### 2. Local-First Sync Queue
Operations that require network access are enqueued when offline and replayed
in order when connectivity returns. The queue is persisted to disk for crash
resilience.

### 3. Local Database
An embedded SQLite database (via aiosqlite + SQLAlchemy) provides offline
storage for:
- Cached provider manifests
- Sync queue
- Desktop settings
- Cached knowledge entries

### 4. Cached Authentication
Credentials are stored in the OS-native credential store (Windows Credential
Manager) and cached for offline authentication. Auth tokens are refreshed
automatically when connectivity returns.

### 5. Graceful Degradation
When offline, the system:
- Disables update checks (they resume on reconnect)
- Disables provider health checks (returns cached status)
- Queues any write operations
- Serves cached read operations from local DB

## Consequences
- All core capabilities work without network access
- No data loss on connectivity transitions
- Transparent sync on reconnect
- Additional storage requirements for local DB
