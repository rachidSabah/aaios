# 07 — Deployment Topology

> **Audience:** operators, DevOps.
> **Purpose:** define the Docker Compose topology, networking, volumes, the path to Kubernetes, and the operational runbook.

---

## 1. Reference deployment

The reference deployment is a single Docker Compose stack on a single host. It is designed to run on:

- **Laptop / desktop** (developer or power user): 16 GB RAM, 4 cores, 50 GB free disk. Runs all services except Qdrant (uses an embedded mode) and Postgres (uses SQLite).
- **Small server** (team of up to 10 users): 32 GB RAM, 8 cores, 200 GB SSD. Runs the full stack.
- **Beefy server** (team of up to 50 users): 64 GB RAM, 16 cores, 500 GB SSD. Runs the full stack plus a worker pool of 4 Claude Code subprocesses and 2 Hermes subprocesses.

Anything beyond 50 concurrent users is out of scope for v1 and is the trigger for the Kubernetes migration (v1.1).

## 2. Compose topology

```mermaid
flowchart LR
    subgraph Host["Host (single VM or bare metal)"]
        subgraph Compose["docker compose"]
            PROXY[nginx<br/>:80 :443 TLS termination]
            WEB[aaios-web<br/>Next.js 16<br/>:3000]
            API[aaios-api<br/>FastAPI + Uvicorn<br/>:8000]
            RUNTIME[aaios-runtime<br/>Supervisor + Agents<br/>:9000 internal]
            HERMES[aaios-hermes<br/>Desktop daemon<br/>headless in v1]
            WORKER[aaios-worker<br/>Background jobs<br/>embeddings, summaries]
            PG[(postgres:16<br/>:5432)]
            QDRANT[(qdrant:1.10<br/>:6333 :6334)]
            REDIS[(redis:7<br/>:6379)]
            OTel[otel-collector<br/>:4317 :4318]
        end
    end

    Internet --> PROXY
    PROXY --> WEB
    PROXY --> API
    API --> RUNTIME
    API --> PG
    API --> REDIS
    RUNTIME --> PG
    RUNTIME --> QDRANT
    RUNTIME --> REDIS
    RUNTIME -.->|JSON-RPC<br/>stdin/stdout| HERMES
    RUNTIME --> OTel
    WORKER --> PG
    WORKER --> QDRANT
    WORKER --> REDIS
    WEB -.->|WebSocket| API
```

### 2.1 Services

| Service | Image | Purpose | Ports exposed | Volumes |
|---------|-------|---------|---------------|---------|
| `nginx` | `nginx:1.27-alpine` | TLS termination, reverse proxy | 80, 443 (host) | `./nginx/conf.d` (RO) |
| `aaios-web` | `ghcr.io/rachidsabah/aaios-web:latest` | Next.js dashboard | 3000 (internal) | — |
| `aaios-api` | `ghcr.io/rachidsabah/aaios-runtime:latest` | FastAPI server | 8000 (internal) | — |
| `aaios-runtime` | `ghcr.io/rachidsabah/aaios-runtime:latest` | Supervisor + agents + tool registry | 9000 (internal) | `./data/runtime` (RW, sandboxed) |
| `aaios-hermes` | `ghcr.io/rachidsabah/aaios-hermes:latest` | Desktop daemon (headless in v1) | — | `/tmp/.X11-unix` (RW) |
| `aaios-worker` | `ghcr.io/rachidsabah/aaios-runtime:latest` | Background jobs | — | — |
| `postgres` | `postgres:16-alpine` | Relational DB + event store + audit log | 5432 (internal) | `./data/postgres` (RW) |
| `qdrant` | `qdrant/qdrant:1.10` | Vector memory | 6333 (internal), 6334 (internal gRPC) | `./data/qdrant` (RW) |
| `redis` | `redis:7-alpine` | Pub/sub + cache + task queue | 6379 (internal) | `./data/redis` (RW) |
| `otel-collector` | `otel/otelcol-contrib:latest` | Telemetry aggregation | 4317, 4318 (internal) | — |

### 2.2 Networking
- All services share a single Docker network (`aaios-net`).
- Only `nginx` exposes host ports (80 and 443).
- Inter-service traffic is unencrypted (the network is isolated). TLS is terminated at `nginx`.
- `aaios-runtime` and `aaios-hermes` communicate over a shared volume (the JSON-RPC pipe) — no network.

### 2.3 Volumes
- `./data/postgres` — Postgres data directory. Backed up nightly via `pg_dump`.
- `./data/qdrant` — Qdrant storage. Backed up nightly via Qdrant snapshot API.
- `./data/redis` — Redis AOF. Recreatable from Postgres + Qdrant; not backed up.
- `./data/runtime` — Supervisor scratch (sandboxed project workspace, plugin installs, MCP server downloads). Recreatable; not backed up.
- `./data/audit` — Audit log (bind-mounted into `aaios-runtime` and `aaios-api`). Append-only. Backed up nightly to S3-compatible storage.

### 2.4 Resource limits

| Service | CPU limit | Memory limit | Notes |
|---------|-----------|--------------|-------|
| `aaios-web` | 1.0 | 512 MB | Next.js Node process |
| `aaios-api` | 2.0 | 1 GB | FastAPI + uvicorn |
| `aaios-runtime` | 4.0 | 4 GB | Supervisor + agent subprocesses |
| `aaios-hermes` | 2.0 | 2 GB | Headless Playwright in v1 |
| `aaios-worker` | 2.0 | 2 GB | Embeddings + summarization |
| `postgres` | 2.0 | 2 GB | shared_buffers=512MB |
| `qdrant` | 2.0 | 2 GB | — |
| `redis` | 0.5 | 256 MB | maxmemory=200mb, allkeys-lru |
| `otel-collector` | 0.5 | 256 MB | — |
| `nginx` | 0.25 | 64 MB | — |

Total reference footprint: ~14 GB RAM, ~14 CPU cores. Fits comfortably on a 16-core / 32 GB server with headroom.

## 3. Configuration

### 3.1 Environment
All runtime configuration is via environment variables, loaded by the Configuration Manager at boot. The `docker-compose.yml` references a `.env` file at the repo root (gitignored, never committed).

```bash
# .env (NEVER commit this file)
AAIOS_ENV=production
AAIOS_SECRET_KEY=<32-byte random base64>
AAIOS_DB_URL=postgresql+asyncpg://aaios:***@postgres:5432/aaios
AAIOS_QDRANT_URL=http://qdrant:6333
AAIOS_REDIS_URL=redis://redis:6379/0

# LLM providers (each is optional; system runs in degraded mode without them)
AAIOS_OPENAI_API_KEY=${secret:openai/api_key}
AAIOS_ANTHROPIC_API_KEY=${secret:anthropic/api_key}
AAIOS_OPENROUTER_API_KEY=${secret:openrouter/api_key}

# OAuth (optional; if unset, local mode is used)
AAIOS_OAUTH_GITHUB_CLIENT_ID=...
AAIOS_OAUTH_GITHUB_CLIENT_SECRET=${secret:oauth/github/client_secret}

# Telemetry (optional)
AAIOS_OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### 3.2 Secret bootstrap
On first boot, if `AAIOS_SECRET_KEY` is unset, the runtime generates one, encrypts it with a passphrase the operator provides interactively (or reads from `/etc/aaios/master.key`), and writes it to `./data/runtime/master.key`. On subsequent boots, the runtime reads the master key, decrypts the secret store, and proceeds.

If the master key is lost, all secrets in the store are unrecoverable. The operator must re-create them. This is documented prominently in the installation guide.

## 4. Health checks

Every service exposes `/healthz` (liveness) and `/readyz` (readiness):

- `/healthz` returns 200 if the process is alive and the event loop is not stuck.
- `/readyz` returns 200 if the process is alive AND all its dependencies are reachable (DB, Redis, Qdrant for the runtime; Postgres for the API).

Docker Compose uses these for restart policies. Nginx uses `/readyz` to decide whether to route traffic to a service.

## 5. Backups

### 5.1 What to back up
- **Postgres:** `pg_dump` nightly, retained 30 days. Includes the event store, the audit log, the configuration, the plugin registry.
- **Qdrant:** snapshot API nightly, retained 30 days. Includes all vector memory.
- **Audit log:** nightly rsync to S3-compatible storage, retained 1 year (compliance).
- **Configuration:** `./config/` directory nightly, retained 30 days.

### 5.2 What not to back up
- **Redis:** all data is recreatable from Postgres.
- **Runtime scratch:** all data is recreatable from Postgres + Qdrant.
- **Plugin binaries:** can be re-downloaded from the marketplace.

### 5.3 Restore
The restore procedure is documented in the runbook:

1. Stop the stack: `docker compose down`.
2. Wipe `./data/`.
3. Restore Postgres from `pg_dump`: `gunzip -c backup.sql.gz | docker compose run --rm postgres psql -U aaios`.
4. Restore Qdrant from snapshot: copy snapshot into `./data/qdrant/snapshots/`, restart Qdrant.
5. Restore audit log and config.
6. Start the stack: `docker compose up -d`.
7. Verify with `aaios doctor` (a CLI command that checks all services, runs a smoke task, and reports).

## 6. Observability

### 6.1 Metrics
- Each service exports Prometheus metrics on `/metrics` (scraped by an optional `prometheus` service).
- Key metrics: `aaios_tasks_active`, `aaios_tasks_completed_total`, `aaios_agent_dispatch_total{agent}`, `aaios_provider_call_total{provider,status}`, `aaios_provider_cost_usd_total{provider}`, `aaios_memory_vectors_total`, `aaios_audit_log_entries_total`, `aaios_permission_denied_total`.

### 6.2 Logs
- All services log structured JSON to stdout. Docker captures stdout.
- The `aaios-api` service additionally writes to `./data/logs/aaios.log` (rotating, 100 MB × 7 files).
- Logs include correlation IDs that match events on the bus.

### 6.3 Traces
- OpenTelemetry traces are exported to the `otel-collector` service, which can forward to Jaeger, Tempo, Honeycomb, or Datadog.
- Every task creates a root span. Every agent dispatch, every tool call, every LLM call creates a child span.

### 6.4 Dashboards
- The built-in AAiOS dashboard has a "Telemetry" page showing real-time metrics and recent traces.
- For production deployments, we recommend a separate Grafana stack (out of scope for v1).

## 7. Path to Kubernetes (v1.1)

The Compose file is structured so the migration to Kubernetes is mechanical:

| Compose service | K8s equivalent |
|-----------------|----------------|
| `aaios-web` | Deployment + Service + Ingress |
| `aaios-api` | Deployment + Service |
| `aaios-runtime` | StatefulSet (needs stable identity for supervisor leader election) |
| `aaios-hermes` | Deployment (with hostNetwork for desktop access, or omitted in server-only deployments) |
| `aaios-worker` | Deployment (HPA on queue depth) |
| `postgres` | StatefulSet + PersistentVolumeClaim (or managed Postgres) |
| `qdrant` | StatefulSet + PersistentVolumeClaim (or Qdrant Cloud) |
| `redis` | StatefulSet (or managed Redis) |
| `otel-collector` | DaemonSet (or managed OTel) |
| `nginx` | Ingress controller (nginx-ingress or Traefik) |

The Helm chart will be developed in v1.1 along with ArgoCD-compatible GitOps manifests. The Compose file remains the primary deployment for v1.

## 8. Operational runbook (summary)

The full runbook is in `docs/operations/runbook.md` (Phase 12 deliverable). The summary:

| Scenario | Action |
|----------|--------|
| Service won't start | `docker compose logs <service>`; check `/healthz` and `/readyz`; check resource limits. |
| Postgres disk full | `pg_vacuum` + `pg_repack` on the event store; consider 90-day retention enforcement. |
| Qdrant slow | Check collection sizes; consider sharding by memory scope. |
| Supervisor stuck | `aaios tasks` to see active tasks; `aaios tasks pause <id>` to pause; restart `aaios-runtime` if needed (state recovers from event log). |
| Hermes crashed | Auto-restarts up to 3×; if exhausted, `docker compose restart aaios-hermes`. |
| LLM provider down | Model Router fails over automatically; check `aaios_provider_call_total` for the failing provider. |
| Plugin crashed | Auto-disabled; `aaios plugins disable <name>` to confirm; check audit log for the crash reason. |
| Audit log tampered | Hash chain verification fails at boot; system refuses to start; operator must investigate. |
| Master key lost | Cannot recover secrets; re-create them; re-issue API keys. |
| Suspected compromise | Rotate all secrets, review audit log for unusual accesses, rebuild from known-good backup. |

## 9. Security baseline for deployment

Before going to production, the operator MUST:

1. Generate a strong `AAIOS_SECRET_KEY` (32+ bytes random).
2. Set `AAIOS_ENV=production` (disables debug endpoints, enables strict CORS).
3. Configure TLS (Let's Encrypt via Certbot, or bring-your-own cert).
4. Configure OAuth (do not run in local mode for a multi-user deployment).
5. Configure backups (Postgres, Qdrant, audit log).
6. Configure the egress allow-list.
7. Review the default RBAC roles and adjust for the organization.
8. Run `aaios doctor` and resolve all warnings.

The `aaios doctor` command (Phase 10) checks all of the above and refuses to mark the system healthy until they are resolved.

---

This concludes the deployment topology. For the build plan that produces everything described here, see [`08-roadmap.md`](08-roadmap.md).
