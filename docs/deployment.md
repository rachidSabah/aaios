# Deployment Guide

## Windows Native (Primary)

### Service Architecture

| Service | Binary | Port | Purpose |
|---------|--------|------|---------|
| AAiOS-API | `python -m uvicorn` | 8000 | REST + WebSocket API |
| AAiOS-Runtime | `python -m supervisor.runtime` | 9000 | Supervisor + Agent Registry + Orchestrator |
| AAiOS-Web | `node web/server.js` | 3000 | Next.js dashboard |
| AAiOS-Worker | `python -m aaios.worker` | — | Background jobs (embeddings, summaries) |
| AAiOS-Hermes | `python -m agents.hermes` | — | Desktop automation (on-demand) |

### File Layout

```
C:\Program Files\AAiOS\          # Binaries (read-only)
%ProgramData%\AAiOS\
  ├─ config\                     # System-wide config
  ├─ data\                       # Postgres, Qdrant, runtime scratch
  ├─ logs\                       # Rotating logs + audit log
  └─ master.key                  # Secret encryption key (ACL: SYSTEM + .\AAiOS)
%APPDATA%\AAiOS\                 # Per-user data (tokens, preferences)
%TEMP%\AAiOS\                    # Temp (cleaned on start)
```

### Service Management

```powershell
# Start all services
Start-Service AAiOS-API, AAiOS-Runtime, AAiOS-Web, AAiOS-Worker

# Stop all services
Stop-Service AAiOS-*

# Check status
Get-Service AAiOS-*

# View logs
Get-Content "$env:ProgramData\AAiOS\logs\aaios-api.log" -Tail 50 -Wait
```

### Backup

```powershell
# Backup Postgres
pg_dump -U aaios -d aaios > backup.sql

# Backup Qdrant (via API)
curl http://localhost:6333/collections | python -m json.tool

# Backup audit log
Copy-Item "$env:ProgramData\AAiOS\logs\audit\" "D:\backup\audit\"

# Backup master key (OFFLINE — USB drive, password manager)
Copy-Item "$env:ProgramData\AAiOS\master.key" "E:\backup\master.key"
```

### Restore

```powershell
Stop-Service AAiOS-*
# Restore Postgres, Qdrant, audit, config, master key
Start-Service AAiOS-*
aaios doctor  # verify
```

## Docker Compose (Secondary)

```bash
# Start
docker compose -f deploy/docker/docker-compose.yml up -d

# Logs
docker compose -f deploy/docker/docker-compose.yml logs -f api

# Stop
docker compose -f deploy/docker/docker-compose.yml down

# Reset (warning: deletes all data)
docker compose -f deploy/docker/docker-compose.yml down -v
```

## Security Baseline

Before going to production:

1. ✅ Generate a strong master key passphrase (20+ chars)
2. ✅ Back up `master.key` to offline storage
3. ✅ Set `env: production` in config
4. ✅ Configure TLS (Let's Encrypt via win-acme, or bring-your-own cert)
5. ✅ Configure OAuth (not local mode for multi-user)
6. ✅ Configure backups (Postgres, Qdrant, audit log)
7. ✅ Configure the egress allow-list
8. ✅ Enable Windows Defender Controlled Folder Access
9. ✅ Apply WDAC policy (enterprise)
10. ✅ Run `aaios doctor` — resolve all warnings

## Monitoring

- **Metrics**: `GET /metrics` (Prometheus format)
- **Health**: `GET /healthz` (liveness), `GET /readyz` (readiness)
- **Logs**: `%ProgramData%\AAiOS\logs\*.log` (structured JSON)
- **Audit**: `%ProgramData%\AAiOS\logs\audit\audit-YYYY-MM.log` (hash-chained)
- **Telemetry**: OpenTelemetry → OTLP collector → Jaeger/Tempo/Honeycomb

## Upgrading

1. Back up (see above)
2. Stop all services
3. Run the new installer (or `git pull && pip install -e .`)
4. Run `aaios doctor`
5. Start services
