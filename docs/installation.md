# Installation Guide

## Prerequisites

### Windows 11 (primary target)
- **Python 3.12+** — [python.org](https://www.python.org/downloads/)
- **Node.js 22 LTS** — [nodejs.org](https://nodejs.org/)
- **pnpm 9+** — `npm install -g pnpm`
- **PostgreSQL 16** (optional — SQLite works for dev/test)
- **Qdrant 1.10+** (optional — only needed for memory features)
- **PowerShell 7+** (pre-installed on Windows 11, or install from [GitHub](https://github.com/PowerShell/PowerShell))

### Linux (v1.1 — secondary target)
- Python 3.12+, Node.js 22 LTS, pnpm 9+
- PostgreSQL 16, Qdrant 1.10+
- bash or zsh

## Quick Start (Development)

### 1. Clone the repository

```powershell
git clone https://github.com/rachidSabah/aaios.git
cd aaios
```

### 2. Set up Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,windows]"
```

### 3. Set up Node.js

```powershell
pnpm install
```

### 4. Verify installation

```powershell
aaios version
aaios doctor
```

### 5. Start the development stack

```powershell
# Start the API server
tasks api

# In another terminal, start the web UI
tasks web
```

The API server runs on `http://127.0.0.1:8000` and the web UI on `http://127.0.0.1:3000`.

## Production Installation (Windows Native)

### Option A: Windows Installer (recommended)

1. Download `AAiOS-Setup-x.y.z.exe` from the [Releases page](https://github.com/rachidSabah/aaios/releases).
2. Run the installer as Administrator.
3. The installer will:
   - Install AAiOS to `C:\Program Files\AAiOS\`
   - Create the `.\AAiOS` service account
   - Set up data directories in `%ProgramData%\AAiOS\`
   - Register Windows Services (AAiOS-API, AAiOS-Runtime, AAiOS-Web, AAiOS-Worker)
   - Generate the master key (you'll be prompted for a passphrase)
   - Configure Windows Defender exclusions
4. Open `http://127.0.0.1:3000` in your browser.

### Option B: Manual Installation

1. Install Python 3.12+, Node.js 22 LTS, PostgreSQL 16, Qdrant.
2. Clone the repository and install dependencies (see Quick Start above).
3. Run `.\deploy\windows\bootstrap.ps1 -Action install`.
4. Run `aaios doctor` to verify.

## Docker Installation (Optional)

```bash
# Clone and start
git clone https://github.com/rachidSabah/aaios.git
cd aaios
cp .env.example .env  # edit with your settings
docker compose -f deploy/docker/docker-compose.yml up -d
```

Services:
- Nginx (reverse proxy, ports 80/443)
- AAiOS Web (Next.js, port 3000)
- AAiOS API (FastAPI, port 8000)
- AAiOS Runtime (Supervisor, port 9000)
- AAiOS Worker (background jobs)
- PostgreSQL 16 (port 5432)
- Qdrant (port 6333)
- Redis (port 6379, optional)
- OpenTelemetry Collector (port 4317)

## Configuration

### Main config file

Location: `%ProgramData%\AAiOS\config\config.yaml` (Windows) or `/etc/aaios/config.yaml` (Linux).

See `config/defaults.yaml` for the full default configuration.

### Environment variables

All config keys can be overridden via environment variables with the `AAiOS_` prefix:

```
AAiOS_DB_URL=postgresql+asyncpg://user:pass@host:5432/aaios
AAiOS_QDRANT_URL=http://localhost:6333
AAiOS_OPENAI_API_KEY=sk-...
```

### Secrets

Secrets are NEVER stored in config files. They're referenced via `${secret:name}` placeholders and resolved from the encrypted Secret Store at access time.

```bash
# Set a secret
aaios config set-secret openai/api_key "sk-..."

# Or via the dashboard (Settings → Secrets)
```

## Verification

After installation, run:

```powershell
aaios doctor
```

This checks:
- All services are running
- Database connectivity
- Qdrant connectivity
- At least one LLM provider configured
- Master key present and ACL-correct
- File system permissions
- Windows Defender exclusions

## Troubleshooting

### API server won't start
- Check `%ProgramData%\AAiOS\logs\aaios-api.log`
- Run `aaios doctor` for automated diagnostics
- Verify port 8000 is not in use: `netstat -an | findstr :8000`

### No LLM providers configured
- Set at least one API key: `aaios config set-secret openai/api_key "sk-..."`
- Or configure a local model: `aaios config set providers.ollama.enabled true`

### Database connection failed
- Verify PostgreSQL is running: `Get-Service postgresql-16`
- Check the connection string in `config.yaml`
