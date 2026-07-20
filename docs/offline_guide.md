# Offline Mode Guide

> Version 1.0.0-rc1

## Overview

The Desktop Runtime supports full offline operation. All core capabilities
work without network access. Changes are automatically synchronised when
connectivity returns.

## What Works Offline

| Capability | Offline Status | Notes |
|-----------|---------------|-------|
| Authentication | ✅ Full | Credentials cached in native store |
| Memory | ✅ Full | Local SQLite database |
| MCP | ✅ Full | Cached provider manifests |
| Execution | ✅ Full | Through local execution engine |
| Workflows | ✅ Full | Cached work plans |
| Mission Control | ✅ Full | Desktop Runtime dashboard |
| Documentation | ✅ Full | Locally cached docs |
| Plugin Execution | ✅ Full | Through desktop plugin loader |
| AI Inference | ✅ Partial | Only local engines (Ollama, llama.cpp) |
| Update Checks | 🔄 Queued | Resumes on reconnect |
| Provider Health | 🔄 Cached | Uses last known status |

## Connectivity States

### Online
- Normal operation
- Update checks run on schedule
- Provider health checks are live
- Sync queue is flushed
- Events published: `desktop.online`

### Offline
- All core capabilities continue working
- Outgoing operations are queued
- Update checks are skipped
- Provider health shows cached status
- Events published: `desktop.offline`

### Transition: Online → Offline
1. OfflineRuntimeManager detects connectivity loss
2. Publishes `desktop.offline` event
3. Notifications shown for all subscribed surfaces
4. Sync queue starts accepting operations
5. All online-only features gracefully degrade

### Transition: Offline → Online
1. OfflineRuntimeManager detects connectivity restoration
2. Publishes `desktop.online` event
3. Sync queue is flushed (operations replayed in order)
4. Update checks resume
5. Provider health checks resume
6. All features return to normal operation

## Configuration

### Connectivity Probes
Configure which URLs are probed (default: github.com, api.github.com, pypi.org):

```python
from services.desktop.offline import OfflineRuntimeManager

offline = OfflineRuntimeManager(
    probe_urls=["https://github.com", "https://api.github.com"],
    probe_interval_s=30.0,  # check every 30 seconds
)
```

### Local Database
The embedded SQLite database is stored at:
- Windows: `%APPDATA%\AAiOS\desktop\db\desktop.db`
- Linux: `~/.local/share/aaios/desktop/db/desktop.db`

### Sync Queue
The sync queue is persisted to:
- `{data_dir}/offline/sync_queue.json`
