<#
.SYNOPSIS
    AAiOS one-click uninstaller for Windows 11.
.DESCRIPTION
    Fully removes AAiOS: stops services, removes venv, deletes data/config/logs,
    uninstalls the npm packages (claude-code), and cleans up.
    Does NOT remove Python, Node.js, or git (system dependencies stay).
.NOTES
    Run from PowerShell:
    irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/uninstall.ps1 | iex
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\AAiOS",
    [switch]$RemoveData,
    [switch]$RemoveAgents
)

$ErrorActionPreference = 'Continue'

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red }

Write-Host @"
╔══════════════════════════════════════════════════╗
║       AAiOS One-Click Uninstaller v1.0.0         ║
╚══════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

Write-Host "Install dir: $InstallDir"
Write-Host "Remove data: $RemoveData (config, data, logs)"
Write-Host "Remove agents: $RemoveAgents (claude-code npm package)"
Write-Host ""

# --- Step 1: Stop any running AAiOS processes ---
Write-Step "Stopping AAiOS processes..."

$pythonProcs = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "aaios|uvicorn|surfaces.api|supervisor.runtime|scripts.start" -ErrorAction SilentlyContinue
}
if ($pythonProcs) {
    $pythonProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-OK "Stopped AAiOS Python processes"
} else {
    Write-OK "No running AAiOS processes found"
}

# Also stop by port
$portProcs = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($portProcs) {
    $portProcs | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-OK "Stopped processes on port 8000"
}

# --- Step 2: Remove Python venv and packages ---
Write-Step "Removing Python environment..."

if (Test-Path "$InstallDir\aaios\.venv") {
    Remove-Item -Recurse -Force "$InstallDir\aaios\.venv" -ErrorAction SilentlyContinue
    Write-OK "Virtual environment removed"
} else {
    Write-OK "No virtual environment found"
}

# Uninstall the aaios pip package
$venvPip = "$InstallDir\aaios\.venv\Scripts\pip.exe"
if (Test-Path $venvPip) {
    & $venvPip uninstall -y aaios 2>$null
}
# Also try system pip
pip uninstall -y aaios 2>$null
Write-OK "AAiOS Python package uninstalled"

# --- Step 3: Remove Node.js packages ---
Write-Step "Removing Node.js packages..."

if (Test-Path "$InstallDir\aaios\node_modules") {
    Remove-Item -Recurse -Force "$InstallDir\aaios\node_modules" -ErrorAction SilentlyContinue
    Write-OK "Node.js packages removed"
} else {
    Write-OK "No node_modules found"
}

# --- Step 4: Optionally remove agent CLIs ---
if ($RemoveAgents) {
    Write-Step "Removing AI agent CLIs..."

    # Uninstall Claude Code CLI
    $claudePath = Get-Command claude -ErrorAction SilentlyContinue
    if ($claudePath) {
        npm uninstall -g @anthropic-ai/claude-code 2>$null
        Write-OK "Claude Code CLI uninstalled"
    } else {
        Write-OK "Claude Code CLI not found"
    }

    # Remove Hermes wrapper
    $hermesPath = "$env:ProgramData\AAiOS\bin\hermes.bat"
    if (Test-Path $hermesPath) {
        Remove-Item $hermesPath -Force -ErrorAction SilentlyContinue
        Write-OK "Hermes wrapper removed"
    }
} else {
    Write-Warn "Skipping agent CLI removal (use -RemoveAgents to remove them)"
}

# --- Step 5: Remove config/data/logs ---
Write-Step "Removing configuration and data..."

$configDir = "$env:ProgramData\AAiOS"
if (Test-Path $configDir) {
    if ($RemoveData) {
        Remove-Item -Recurse -Force $configDir -ErrorAction SilentlyContinue
        Write-OK "Removed $configDir (config, data, logs)"
    } else {
        Write-Warn "Keeping $configDir (use -RemoveData to delete config/data/logs)"
    }
} else {
    Write-OK "No system config directory found"
}

# Remove user-level config
$userConfig = "$env:APPDATA\AAiOS"
if (Test-Path $userConfig) {
    Remove-Item -Recurse -Force $userConfig -ErrorAction SilentlyContinue
    Write-OK "Removed user config ($userConfig)"
}

# Remove temp
$tempDir = "$env:TEMP\AAiOS"
if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
    Write-OK "Removed temp directory"
}

# --- Step 6: Remove the repository ---
Write-Step "Removing AAiOS repository..."

if (Test-Path "$InstallDir\aaios") {
    Remove-Item -Recurse -Force "$InstallDir\aaios" -ErrorAction SilentlyContinue
    if (Test-Path "$InstallDir\aaios") {
        Write-Warn "Could not fully remove $InstallDir\aaios (may be in use). Close all terminals and retry."
    } else {
        Write-OK "Repository removed"
    }
} else {
    Write-OK "Repository not found"
}

# Remove the parent directory if empty
if (Test-Path $InstallDir) {
    $children = Get-ChildItem $InstallDir -ErrorAction SilentlyContinue
    if (-not $children) {
        Remove-Item $InstallDir -ErrorAction SilentlyContinue
        Write-OK "Removed empty parent directory"
    }
}

# --- Step 7: Clean up environment variables ---
Write-Step "Cleaning up environment..."

# Remove PATH entries for AAiOS (from user PATH)
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -match "AAiOS") {
    $cleanPath = ($userPath -split ';' | Where-Object { $_ -notmatch 'AAiOS' }) -join ';'
    [System.Environment]::SetEnvironmentVariable("Path", $cleanPath, "User")
    Write-OK "Removed AAiOS from user PATH"
}

# --- Done ---
Write-Host @"
╔══════════════════════════════════════════════════╗
║          Uninstallation Complete!                ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  AAiOS has been fully removed.                   ║
║                                                  ║
║  System dependencies (Python, Node.js, git)      ║
║  were NOT removed.                               ║
║                                                  ║
║  To reinstall:                                   ║
║  irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex
║                                                  ║
╚══════════════════════════════════════════════════╝
"@ -ForegroundColor Green
