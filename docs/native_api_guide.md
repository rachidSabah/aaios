# Native API Guide

> Version 1.0.0-rc1

## Overview

The Desktop Runtime exposes 22 REST API endpoints under `/api/v1/desktop/`
for querying and controlling the desktop application state.

## Endpoints

### Status
```
GET /api/v1/desktop/status
```
Returns the Desktop Runtime boot status, service list, and version.

### Diagnostics
```
GET /api/v1/desktop/diagnostics
```
Runs all diagnostic checks and returns results with pass/fail/warn status.

### Performance Monitor
```
GET /api/v1/desktop/perfmon
GET /api/v1/desktop/perfmon/history?metric=cpu_percent&limit=100
```
Returns current performance metrics and historical time series.

### Offline Mode
```
GET /api/v1/desktop/offline
```
Returns online/offline status and sync queue length.

### Local AI
```
GET /api/v1/desktop/local-ai
```
Returns detected local AI engines (Ollama, llama.cpp, LocalAI) with health.

### Notifications
```
GET /api/v1/desktop/notifications?limit=50&level=warning
```
Returns recent desktop notifications with optional filtering.

### Windows & Workspaces
```
GET /api/v1/desktop/windows
GET /api/v1/desktop/workspaces
```
Returns open window states and workspace configurations.

### Plugins
```
GET /api/v1/desktop/plugins
```
Returns installed desktop plugins with metadata.

### Logs
```
GET /api/v1/desktop/logs?limit=100&level=error
```
Returns recent log entries.

### Updates
```
GET /api/v1/desktop/updates
POST /api/v1/desktop/updates/check
```
Returns update status and triggers an update check.

### Credentials
```
GET /api/v1/desktop/credentials
```
Returns stored credential keys (NOT secret values).

### System
```
GET /api/v1/desktop/system
GET /api/v1/desktop/services
```
Returns platform information and running service names.

## Usage Examples

### Python
```python
import httpx

async with httpx.AsyncClient() as cli:
    resp = await cli.get("http://localhost:8000/api/v1/desktop/status")
    data = resp.json()
    print(data["booted"], data["version"])
```

### PowerShell
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/desktop/status"
```

### curl
```bash
curl http://localhost:8000/api/v1/desktop/status | jq .
```
