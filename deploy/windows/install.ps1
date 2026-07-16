<#
.SYNOPSIS
    AAiOS v5.3.2 one-click installer for Windows 11.
.DESCRIPTION
    Installs AAiOS with all dependencies: Python 3.12, Node.js 22, pnpm, PostgreSQL, Qdrant.
    Sets up the virtual environment, installs packages, and runs `aaios install`.

    When AAiOS is already installed, an interactive menu lets the user choose:
      [1] Update   — pull latest from GitHub
      [2] Repair   — rebuild venv / re-install packages (keeps data)
      [3] Uninstall — fully remove AAiOS (streams the uninstall.ps1 script)
      [4] Exit     — cancel, do nothing
.NOTES
    Run from PowerShell as Administrator:
    irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex

    With options (must use -Mode etc.):
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1))) -Mode silent -Workspace 'D:\AAiOS'
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\AAiOS",
    [string]$Mode = "interactive",
    [string]$Workspace = "",
    [string]$Profile = "",
    [switch]$Force,
    [switch]$SkipDeps,
    [switch]$Interactive,
    [switch]$Silent,
    [switch]$Minimal,
    [switch]$Developer,
    [switch]$Enterprise,
    [switch]$Portable,
    [switch]$Offline,
    [switch]$Repair,
    [switch]$Upgrade,
    [switch]$Validate
)

$ErrorActionPreference = 'Stop'
$env:NODE_OPTIONS = '--no-deprecation'
$repoUrl  = 'https://github.com/rachidSabah/aaios.git'
$rawBase  = 'https://raw.githubusercontent.com/rachidSabah/aaios/main'

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  ✓ $msg"  -ForegroundColor Green  }
function Write-Warn($msg) { Write-Host "  ⚠ $msg"  -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  ✗ $msg"  -ForegroundColor Red    }

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ── Banner ───────────────────────────────────────────────────────────────────
Write-Host @"
╔═══════════════════════════════════════════════════════╗
║         AAiOS One-Click Installer v1.0.0              ║
║   Agentic AI Operating System — Windows 11            ║
╚═══════════════════════════════════════════════════════╝
"@ -ForegroundColor Magenta

Write-Host "Install directory : $InstallDir"
Write-Host "Skip dependencies : $SkipDeps"
Write-Host ""

# ── Administrator check ──────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin -and -not $SkipDeps) {
    Write-Warn "Not running as Administrator. Dependency installation may fail."
    Write-Warn "Re-run as Admin: Start-Process PowerShell -Verb RunAs"
}

# ── Existing-install menu ────────────────────────────────────────────────────
if ((Test-Path "$InstallDir\aaios") -and -not $Force) {

    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "  ║   AAiOS is already installed.                            ║" -ForegroundColor Yellow
    Write-Host "  ║   $InstallDir\aaios" -ForegroundColor Yellow
    Write-Host "  ╠══════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
    Write-Host "  ║  What would you like to do?                              ║" -ForegroundColor Yellow
    Write-Host "  ║                                                          ║" -ForegroundColor Yellow
    Write-Host "  ║   [1]  Update     — pull latest from GitHub              ║" -ForegroundColor Cyan
    Write-Host "  ║   [2]  Repair     — rebuild env, re-install (keep data)  ║" -ForegroundColor Cyan
    Write-Host "  ║   [3]  Uninstall  — fully remove AAiOS                   ║" -ForegroundColor Red
    Write-Host "  ║   [4]  Exit       — cancel, do nothing                   ║" -ForegroundColor DarkGray
    Write-Host "  ║                                                          ║" -ForegroundColor Yellow
    Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""

    do {
        $choice = Read-Host "  Enter choice [1/2/3/4]"
    } while ($choice -notin @('1','2','3','4'))

    switch ($choice) {

        '1' {   # ── Update ───────────────────────────────────────────────
            Write-Step "Updating AAiOS repository..."
            Set-Location "$InstallDir\aaios"
            git pull origin main
            Write-OK "Repository updated to latest"
            Set-Location "$InstallDir\aaios"
            # Falls through to re-run setup (pip install, bind-agents, etc.)
        }

        '2' {   # ── Repair ───────────────────────────────────────────────
            Write-Step "Repairing AAiOS (your data is kept)..."
            Set-Location "$InstallDir\aaios"
            if (Test-Path ".venv") {
                Remove-Item -Recurse -Force ".venv" -ErrorAction SilentlyContinue
                Write-OK "Cleared old virtual environment"
            }
            # Falls through to re-create venv and install packages
        }

        '3' {   # ── Uninstall ─────────────────────────────────────────────
            Write-Host ""
            Write-Host "  ┌─ Uninstall options ────────────────────────────────┐" -ForegroundColor Red
            Write-Host "  │                                                    │" -ForegroundColor Red
            Write-Host "  │  Remove user config, data and logs too?            │" -ForegroundColor Yellow
            Write-Host "  │    [Y]  Yes — delete everything                    │" -ForegroundColor Red
            Write-Host "  │    [N]  No  — keep config/data (default)           │" -ForegroundColor Cyan
            $removeData = Read-Host "  │  Choice [Y/N]"

            Write-Host "  │                                                    │" -ForegroundColor Red
            Write-Host "  │  Remove AI agent CLIs (claude, hermes) too?        │" -ForegroundColor Yellow
            Write-Host "  │    [Y]  Yes — uninstall agent tools                │" -ForegroundColor Red
            Write-Host "  │    [N]  No  — keep them (default)                  │" -ForegroundColor Cyan
            $removeAgents = Read-Host "  │  Choice [Y/N]"
            Write-Host "  └────────────────────────────────────────────────────┘" -ForegroundColor Red
            Write-Host ""

            $uninstallArgs = @()
            if ($removeData   -in @('y','Y')) { $uninstallArgs += '-RemoveData'   }
            if ($removeAgents -in @('y','Y')) { $uninstallArgs += '-RemoveAgents' }

            $uninstallUrl = "$rawBase/deploy/windows/uninstall.ps1"
            Write-Step "Downloading and running uninstaller..."
            $uninstallScript = (Invoke-RestMethod -Uri $uninstallUrl)
            & ([scriptblock]::Create($uninstallScript)) @uninstallArgs

            Write-Host ""
            Write-Host "Press any key to close..." -ForegroundColor DarkGray
            try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { Start-Sleep 5 }
            Exit 0
        }

        '4' {   # ── Exit ─────────────────────────────────────────────────
            Write-Host ""
            Write-Host "  Cancelled — no changes were made." -ForegroundColor DarkGray
            Write-Host ""
            Write-Host "Press any key to close..." -ForegroundColor DarkGray
            try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { Start-Sleep 3 }
            Exit 0
        }
    }

    # After Update / Repair we fall through here and continue the setup below.
    Set-Location "$InstallDir\aaios"

} elseif ($Force -and (Test-Path "$InstallDir\aaios")) {
    Write-Warn "Existing installation found. Removing (--Force)..."
    Remove-Item -Recurse -Force "$InstallDir\aaios"
}

# ── Step 1: Install system dependencies ──────────────────────────────────────
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

# ── Step 2: Clone repository (fresh install only) ────────────────────────────
if (-not (Test-Path "$InstallDir\aaios")) {
    Write-Step "Cloning AAiOS repository..."
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Set-Location $InstallDir
    git clone $repoUrl
    Write-OK "Repository cloned to $InstallDir\aaios"
}

Set-Location "$InstallDir\aaios"

# ── Step 3: Python virtual environment ───────────────────────────────────────
Write-Step "Setting up Python environment..."

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Write-OK "Virtual environment created"
} else {
    Write-OK "Virtual environment exists"
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
Write-Host "Installing Python packages..." -ForegroundColor Yellow
pip install -e ".[dev,windows]"
if ($LASTEXITCODE -ne 0) {
    Write-Err "Failed to install Python packages. Please check the errors above."
    Exit 1
}
Write-OK "Python packages installed"

# ── Step 4: Node.js dependencies ─────────────────────────────────────────────
Write-Step "Setting up Node.js environment..."

pnpm install 2>&1 | Out-Null
Write-OK "Node.js packages installed"

# ── Step 5: Agent detection & binding ────────────────────────────────────────
Write-Step "Detecting and binding AI agents..."

$claudeProxy = $null
$claudeKey   = $null
$args | ForEach-Object {
    if ($_ -match '--claude-proxy-url=(.+)') { $claudeProxy = $matches[1] }
    if ($_ -match '--claude-api-key=(.+)')   { $claudeKey   = $matches[1] }
}
if (-not $claudeProxy -and $env:ANTHROPIC_BASE_URL) { $claudeProxy = $env:ANTHROPIC_BASE_URL }
if (-not $claudeKey   -and $env:ANTHROPIC_API_KEY)  { $claudeKey   = $env:ANTHROPIC_API_KEY  }

$bindArgs = @("scripts/bind_agents.py", "--install-missing")
if ($claudeProxy) {
    $bindArgs += @("--claude-proxy-url", $claudeProxy)
    Write-Host "  Claude Code proxy: $claudeProxy" -ForegroundColor Yellow
}
if ($claudeKey) { $bindArgs += @("--claude-api-key", $claudeKey) }

python $bindArgs 2>&1 | ForEach-Object { Write-Host "  $_" }
Write-OK "Agent detection and binding complete"

# ── Step 6: Configuration ────────────────────────────────────────────────────
Write-Step "Setting up configuration..."

$configDir = "$env:ProgramData\AAiOS\config"
$dataDir   = "$env:ProgramData\AAiOS\data"
$logDir    = "$env:ProgramData\AAiOS\logs"

New-Item -ItemType Directory -Force -Path $configDir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir   | Out-Null
New-Item -ItemType Directory -Force -Path $logDir    | Out-Null

if (-not (Test-Path "$configDir\config.yaml")) {
    Copy-Item "config\defaults.yaml" "$configDir\config.yaml"
    Write-OK "Default config copied to $configDir\config.yaml"
} else {
    Write-OK "Config already exists at $configDir\config.yaml"
}

# ── Step 7: Verify ───────────────────────────────────────────────────────────
Write-Step "Verifying installation..."

$aaiosExe = ".\.venv\Scripts\aaios.exe"
$oldErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

if (Test-Path $aaiosExe) {
    $version = & $aaiosExe version 2>&1
} else {
    $version = python -m surfaces.cli version 2>&1
}

$ErrorActionPreference = $oldErrorAction

if ($LASTEXITCODE -ne 0 -or $version -match "Traceback") {
    Write-Err "Verification failed. Output:"
    Write-Host "  $version" -ForegroundColor Red
    Exit 1
} else {
    Write-OK "AAiOS installed: $version"
}

# ── Register aaios.exe in user PATH ─────────────────────────────────────────
$aaiosScripts = (Resolve-Path ".\.venv\Scripts").Path
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$aaiosScripts*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$userPath;$aaiosScripts", "User")
    $env:Path = "$env:Path;$aaiosScripts"
    Write-OK "aaios added to PATH (effective in new terminals)"
} else {
    Write-OK "aaios already in PATH"
}

# ── Run aaios install ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Running aaios install (mode: $Mode)..." -ForegroundColor Yellow

$resolvedMode = $Mode
if ($Interactive) { $resolvedMode = "interactive" }
elseif ($Silent)   { $resolvedMode = "silent"      }
elseif ($Minimal)  { $resolvedMode = "minimal"     }
elseif ($Developer){ $resolvedMode = "developer"   }
elseif ($Enterprise){$resolvedMode = "enterprise"  }
elseif ($Portable) { $resolvedMode = "portable"    }
elseif ($Offline)  { $resolvedMode = "offline"     }
elseif ($Repair)   { $resolvedMode = "repair"      }
elseif ($Upgrade)  { $resolvedMode = "upgrade"     }
elseif ($Validate) { $resolvedMode = "validate"    }

$installArgs = @("install", "--mode", $resolvedMode)
if ($Workspace) { $installArgs += @("--workspace", $Workspace) }
if ($Profile)   { $installArgs += @("--profile",   $Profile)   }
if ($Force -or $Repair) { $installArgs += "--force" }
& python -m surfaces.cli @installArgs

# ── Done ─────────────────────────────────────────────────────────────────────
$installPath = "$InstallDir\aaios"
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          AAiOS v5.3.2 — Installation Complete!                  ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Install dir : $installPath" -ForegroundColor Green
Write-Host "║  Config      : $env:ProgramData\AAiOS\config\config.yaml" -ForegroundColor Green
Write-Host "║  Data        : $env:ProgramData\AAiOS\data\" -ForegroundColor Green
Write-Host "║  Logs        : $env:ProgramData\AAiOS\logs\" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  HOW TO RUN AAIOS                                                ║" -ForegroundColor Cyan
Write-Host "║                                                                  ║" -ForegroundColor Cyan
Write-Host "║  1. Open a NEW PowerShell window, then run:                     ║" -ForegroundColor Cyan
Write-Host "║       aaios start                                                ║" -ForegroundColor Cyan
Write-Host "║                                                                  ║" -ForegroundColor Cyan
Write-Host "║  2. Browser opens automatically:                                 ║" -ForegroundColor Cyan
Write-Host "║       http://localhost:20128  (9router dashboard)                ║" -ForegroundColor Cyan
Write-Host "║       http://localhost:8000/docs  (AAiOS API docs)               ║" -ForegroundColor Cyan
Write-Host "║                                                                  ║" -ForegroundColor Cyan
Write-Host "║  3. CLI quick-start:                                             ║" -ForegroundColor Cyan
Write-Host "║       aaios --help                                               ║" -ForegroundColor Cyan
Write-Host "║       aaios doctor                                               ║" -ForegroundColor Cyan
Write-Host "║       aaios run `"your goal here`"                                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Offer to launch now
Write-Host "Press ENTER to launch AAiOS now in a new window, or type 'n' + ENTER to skip." -ForegroundColor Yellow
try   { $startNow = [System.Console]::ReadLine() }
catch { $startNow = 'n' }

if ($startNow -ne 'n' -and $startNow -ne 'N') {
    $launchCmd = "Set-Location '$installPath'; & .\.venv\Scripts\Activate.ps1; python scripts\start.py"
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $launchCmd
    Write-Host ""
    Write-Host "  AAiOS is starting — check the new window." -ForegroundColor Green
    Write-Host "  Dashboard → http://localhost:20128"         -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  Run 'aaios start' in any new PowerShell window to start AAiOS." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Press any key to close this installer..." -ForegroundColor DarkGray
try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { Start-Sleep -Seconds 10 }