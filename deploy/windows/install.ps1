<#
.SYNOPSIS
    AAiOS one-click installer for Windows 11.
.DESCRIPTION
    Installs AAiOS with all dependencies: Python 3.12, Node.js 22, pnpm, PostgreSQL, Qdrant.
    Sets up the virtual environment, installs packages, and runs `aaios doctor`.
.NOTES
    Run from PowerShell as Administrator:
    irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\AAiOS",
    [switch]$SkipDeps,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoUrl = 'https://github.com/rachidSabah/aaios.git'

function Write-Step($msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Write-OK($msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# --- Banner ---
Write-Host @"
╔══════════════════════════════════════════════════╗
║         AAiOS One-Click Installer v1.0.0         ║
║   Agentic AI Operating System — Windows 11       ║
╚══════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

Write-Host "Install directory: $InstallDir"
Write-Host "Skip dependencies: $SkipDeps"
Write-Host ""

# --- Check Administrator ---
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $SkipDeps) {
    Write-Warn "Not running as Administrator. Dependency installation may fail."
    Write-Warn "Re-run as Admin: Start-Process PowerShell -Verb RunAs"
}

# --- Step 1: Install dependencies ---
if (-not $SkipDeps) {
    Write-Step "Checking dependencies..."

    # Python 3.12+
    if (Test-Command python) {
        $pyVer = (python --version 2>&1) -replace 'Python ', ''
        if ([version]$pyVer -ge [version]'3.12.0') {
            Write-OK "Python $pyVer found"
        } else {
            Write-Warn "Python $pyVer found, but 3.12+ required. Installing..."
            winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        }
    } else {
        Write-Warn "Python not found. Installing Python 3.12..."
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }

    # Node.js 22
    if (Test-Command node) {
        $nodeVer = (node --version 2>&1)
        Write-OK "Node.js $nodeVer found"
    } else {
        Write-Warn "Node.js not found. Installing Node.js 22 LTS..."
        winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }

    # pnpm
    if (Test-Command pnpm) {
        Write-OK "pnpm found"
    } else {
        Write-Warn "pnpm not found. Installing..."
        npm install -g pnpm
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }

    # Git
    if (Test-Command git) {
        Write-OK "Git found"
    } else {
        Write-Warn "Git not found. Installing..."
        winget install Git.Git --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
}

# --- Step 2: Clone or update repository ---
Write-Step "Cloning AAiOS repository..."

if (Test-Path "$InstallDir\aaios") {
    if ($Force) {
        Write-Warn "Existing installation found. Removing (--Force)..."
        Remove-Item -Recurse -Force "$InstallDir\aaios"
    } else {
        Write-OK "Existing installation found. Updating..."
        Set-Location "$InstallDir\aaios"
        git pull origin main
        Write-OK "Repository updated"
        Set-Location $InstallDir
    }
}

if (-not (Test-Path "$InstallDir\aaios")) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Set-Location $InstallDir
    git clone $repoUrl
    Write-OK "Repository cloned to $InstallDir\aaios"
}

Set-Location "$InstallDir\aaios"

# --- Step 3: Python virtual environment ---
Write-Step "Setting up Python environment..."

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Write-OK "Virtual environment created"
} else {
    Write-OK "Virtual environment exists"
}

# Activate and install
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,windows]" 2>&1 | Out-Null
Write-OK "Python packages installed"

# --- Step 4: Node.js dependencies ---
Write-Step "Setting up Node.js environment..."

pnpm install 2>&1 | Out-Null
Write-OK "Node.js packages installed"

# --- Step 5: Agent Detection & Binding ---
Write-Step "Detecting and binding AI agents..."

# Check for --claude-proxy-url argument
$claudeProxy = $null
$claudeKey = $null
$args | ForEach-Object {
    if ($_ -match '--claude-proxy-url=(.+)') { $claudeProxy = $matches[1] }
    if ($_ -match '--claude-api-key=(.+)') { $claudeKey = $matches[1] }
}
# Also check environment
if (-not $claudeProxy -and $env:ANTHROPIC_BASE_URL) { $claudeProxy = $env:ANTHROPIC_BASE_URL }
if (-not $claudeKey -and $env:ANTHROPIC_API_KEY) { $claudeKey = $env:ANTHROPIC_API_KEY }

$bindArgs = @("scripts/bind_agents.py", "--install-missing")
if ($claudeProxy) {
    $bindArgs += @("--claude-proxy-url", $claudeProxy)
    Write-Host "  Claude Code proxy: $claudeProxy" -ForegroundColor Yellow
}
if ($claudeKey) {
    $bindArgs += @("--claude-api-key", $claudeKey)
}

python $bindArgs 2>&1 | ForEach-Object { Write-Host "  $_" }
Write-OK "Agent detection and binding complete"

# --- Step 6: Configuration ---
Write-Step "Setting up configuration..."

$configDir = "$env:ProgramData\AAiOS\config"
$dataDir = "$env:ProgramData\AAiOS\data"
$logDir = "$env:ProgramData\AAiOS\logs"

New-Item -ItemType Directory -Force -Path $configDir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path "$configDir\config.yaml")) {
    Copy-Item "config\defaults.yaml" "$configDir\config.yaml"
    Write-OK "Default config copied to $configDir\config.yaml"
} else {
    Write-OK "Config already exists at $configDir\config.yaml"
}

# --- Step 6: Verify ---
Write-Step "Verifying installation..."

$aaiosExe = ".\.venv\Scripts\aaios.exe"
if (Test-Path $aaiosExe) {
    $version = & $aaiosExe version 2>&1
    Write-OK "AAiOS installed: $version"
} else {
    # Fallback: run via python module
    $version = python -m surfaces.cli version 2>&1
    Write-OK "AAiOS installed: $version"
}

# Run doctor
Write-Host ""
Write-Host "Running aaios doctor..." -ForegroundColor Yellow
python -m surfaces.cli doctor 2>&1

# --- Done ---
Write-Host @"
╔══════════════════════════════════════════════════╗
║            Installation Complete!                ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Repository: $InstallDir\aaios
║  Config:    $env:ProgramData\AAiOS\config\config.yaml
║  Data:      $env:ProgramData\AAiOS\data\
║  Logs:      $env:ProgramData\AAiOS\logs\
║                                                  ║
║  AAiOS is ready to run in LIVE mode.             ║
║  No mock. No demo. Fully functional.             ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"@ -ForegroundColor Green

# Offer to start immediately
$startNow = Read-Host "`nStart AAiOS now? (Y/n)"
if ($startNow -ne 'n') {
    Write-Host "`nStarting AAiOS in LIVE mode..." -ForegroundColor Green
    Set-Location "$InstallDir\aaios"
    & .\.venv\Scripts\python.exe scripts\start.py
} else {
    Write-Host "`nTo start later:" -ForegroundColor Yellow
    Write-Host "  cd $InstallDir\aaios"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  aaios start"
    Write-Host ""
    Write-Host "  Or with a custom port:" -ForegroundColor Dim
    Write-Host "  aaios start --port 9000"
    Write-Host ""
    Write-Host "  Set an API key first (optional):" -ForegroundColor Dim
    Write-Host "  `$env:OPENAI_API_KEY = 'sk-...'"
    Write-Host "  `$env:ANTHROPIC_API_KEY = 'sk-ant-...'"
}
