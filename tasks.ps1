# AAiOS task runner (Windows PowerShell 7+)
# ============================================
# Usage:
#   .\tasks.ps1 <command>
#   .\tasks.ps1 dev          # start dev stack (API + web)
#   .\tasks.ps1 test         # run all tests
#   .\tasks.ps1 lint         # ruff + mypy + bandit + eslint
#   .\tasks.ps1 check        # lint + test + typecheck (run before pushing)
#   .\tasks.ps1 build        # build all artifacts
#   .\tasks.ps1 clean        # remove build/test artifacts
#   .\tasks.ps1 install-windows  # build the Windows installer
#   .\tasks.ps1 help         # list all commands
#
# Requires:
#   - Python 3.12+ in PATH (or in .venv)
#   - Node 22+ and pnpm 9+ in PATH (for web commands)
#   - PowerShell 7+ (pwsh)

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $PSScriptRoot).Path

function Invoke-Section($name) {
    Write-Host ""
    Write-Host "==> $name" -ForegroundColor Cyan
}

function Invoke-Python {
    # Prefer .venv if it exists, otherwise system python
    if ($IsWindows -or $env:OS -eq 'Windows_NT') {
        $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    } else {
        $venvPython = Join-Path $root '.venv/bin/python'
    }
    if (Test-Path $venvPython) {
        & $venvPython @args
    } else {
        & python @args
    }
}

function Invoke-Task {
    switch ($Command.ToLower()) {
        'help' {
            Write-Host "AAiOS task runner (PowerShell)"
            Write-Host ""
            Write-Host "Commands:"
            Write-Host "  dev                Start dev stack (API + Next.js)"
            Write-Host "  api                Start API server only"
            Write-Host "  web                Start Next.js dev server only"
            Write-Host "  test               Run all Python tests"
            Write-Host "  test-unit          Run unit tests only"
            Write-Host "  test-integration   Run integration tests only"
            Write-Host "  test-e2e           Run end-to-end tests"
            Write-Host "  test-web           Run web (Vitest) tests"
            Write-Host "  test-offline       Run tests with no network (mocked providers)"
            Write-Host "  lint               Ruff + mypy + bandit + eslint"
            Write-Host "  typecheck          TypeScript typecheck (web)"
            Write-Host "  format             Ruff format + Prettier"
            Write-Host "  check              Lint + typecheck + test (run before pushing)"
            Write-Host "  build              Build wheel + Next.js build"
            Write-Host "  build-wheel        Build Python wheel only"
            Write-Host "  build-web          Build Next.js only"
            Write-Host "  install-windows    Build the Windows installer (.exe) via Inno Setup"
            Write-Host "  docker-up          Start the optional Docker Compose stack"
            Write-Host "  docker-down        Stop the Docker Compose stack"
            Write-Host "  clean              Remove build/test artifacts"
            Write-Host "  venv               Create .venv with dev extras"
            Write-Host "  install            Install Python deps + pnpm install"
            Write-Host "  doctor             Run 'aaios doctor'"
            Write-Host "  version            Print AAiOS version"
        }

        'venv' {
            Invoke-Section 'Create virtual environment'
            python -m venv .venv
            if ($IsWindows -or $env:OS -eq 'Windows_NT') {
                & .\.venv\Scripts\python.exe -m pip install --upgrade pip
                & .\.venv\Scripts\pip.exe install -e ".[dev,windows]"
            } else {
                & ./.venv/bin/python -m pip install --upgrade pip
                & ./.venv/bin/pip install -e ".[dev,linux]"
            }
            Write-Host "✓ Virtual environment created at .venv" -ForegroundColor Green
        }

        'install' {
            Invoke-Section 'Install Python dependencies'
            Invoke-Python -m pip install --upgrade pip
            Invoke-Python -m pip install -e ".[dev,windows]"
            Invoke-Section 'Install pnpm dependencies'
            pnpm install
            Write-Host "✓ All dependencies installed" -ForegroundColor Green
        }

        'dev' {
            Invoke-Section 'Start dev stack (Phase 2 stub)'
            Write-Host "Starting API server on http://127.0.0.1:8000 ..."
            Write-Host "Starting Next.js dev server on http://127.0.0.1:3000 ..."
            Write-Host "Press Ctrl+C to stop both."
            # Phase 2: start both, kill both on Ctrl+C
            $api = Start-Process -PassThru -NoNewWindow -FilePath (Invoke-Python) -ArgumentList '-m', 'uvicorn', 'surfaces.api.app:app', '--reload', '--host', '127.0.0.1', '--port', '8000'
            $web = Start-Process -PassThru -NoNewWindow -FilePath 'pnpm' -ArgumentList '--filter', '@aaios/web', 'dev'
            try {
                Wait-Process -Id $api.Id
            } finally {
                Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
                Stop-Process -Id $web.Id -ErrorAction SilentlyContinue
            }
        }

        'api' {
            Invoke-Python -m uvicorn surfaces.api.app:app --reload --host 127.0.0.1 --port 8000
        }

        'web' {
            pnpm --filter '@aaios/web' dev
        }

        'test' {
            Invoke-Section 'Run all Python tests'
            Invoke-Python -m pytest
        }

        'test-unit' {
            Invoke-Python -m pytest tests/unit
        }

        'test-integration' {
            Invoke-Python -m pytest tests/integration
        }

        'test-e2e' {
            Invoke-Python -m pytest tests/e2e
        }

        'test-web' {
            pnpm --filter '@aaios/web' test
        }

        'test-offline' {
            Invoke-Python -m pytest -m offline
        }

        'lint' {
            Invoke-Section 'Ruff (lint)'
            Invoke-Python -m ruff check .
            Invoke-Section 'Ruff (format check)'
            Invoke-Python -m ruff format --check .
            Invoke-Section 'Mypy'
            Invoke-Python -m mypy
            Invoke-Section 'Bandit'
            Invoke-Python -m bandit -c pyproject.toml -r core services agents supervisor orchestrator surfaces/api surfaces/cli
            Invoke-Section 'ESLint (web)'
            pnpm --filter '@aaios/web' lint
        }

        'typecheck' {
            Invoke-Section 'TypeScript typecheck (web)'
            pnpm --filter '@aaios/web' typecheck
        }

        'format' {
            Invoke-Section 'Ruff format'
            Invoke-Python -m ruff format .
            Invoke-Section 'Ruff fix'
            Invoke-Python -m ruff check --fix .
            Invoke-Section 'Prettier'
            pnpm exec prettier --write .
        }

        'check' {
            & $PSCommandPath lint
            & $PSCommandPath typecheck
            & $PSCommandPath test
            Write-Host ""
            Write-Host "✓ All checks passed" -ForegroundColor Green
        }

        'build' {
            & $PSCommandPath build-wheel
            & $PSCommandPath build-web
        }

        'build-wheel' {
            Invoke-Section 'Build Python wheel'
            Invoke-Python -m pip install --upgrade hatch
            Invoke-Python -m hatch build
        }

        'build-web' {
            Invoke-Section 'Build Next.js'
            pnpm --filter '@aaios/web' build
        }

        'install-windows' {
            Invoke-Section 'Build Windows installer (Inno Setup)'
            Write-Host "Phase 2 stub: Inno Setup compile will run here in Phase 14."
            Write-Host "Verifying deploy/windows/aaios.iss exists..."
            if (-not (Test-Path 'deploy/windows/aaios.iss')) {
                throw 'deploy/windows/aaios.iss not found'
            }
            Write-Host "✓ aaios.iss present" -ForegroundColor Green
            # Real command (Phase 14):
            # & 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' deploy\windows\aaios.iss
        }

        'docker-up' {
            Invoke-Section 'Start Docker Compose stack (optional path)'
            docker compose -f deploy/docker/docker-compose.yml up -d
        }

        'docker-down' {
            Invoke-Section 'Stop Docker Compose stack'
            docker compose -f deploy/docker/docker-compose.yml down
        }

        'clean' {
            Invoke-Section 'Remove build/test artifacts'
            $paths = @(
                '.mypy_cache', '.ruff_cache', '.pytest_cache', 'coverage',
                'build', 'dist', '*.egg-info', 'surfaces/web/.next',
                'surfaces/web/out', 'surfaces/web/coverage', 'surfaces/web/test-results'
            )
            foreach ($p in $paths) {
                Get-ChildItem -Path $root -Filter $p -Recurse -Directory -ErrorAction SilentlyContinue |
                    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-Host "✓ Cleaned" -ForegroundColor Green
        }

        'doctor' {
            Invoke-Python -m surfaces.cli doctor
        }

        'version' {
            Invoke-Python -m surfaces.cli version
        }

        default {
            Write-Host "Unknown command: $Command" -ForegroundColor Red
            Write-Host "Run '.\tasks.ps1 help' for the list of commands."
            exit 1
        }
    }
}

Invoke-Task
