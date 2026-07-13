#!/usr/bin/env bash
# AAiOS task runner (Linux / macOS / WSL)
# ========================================
# Usage:
#   ./tasks.sh <command>
#   ./tasks.sh dev             # start dev stack (API + web)
#   ./tasks.sh test             # run all tests
#   ./tasks.sh lint             # ruff + mypy + bandit + eslint
#   ./tasks.sh check            # lint + test + typecheck (run before pushing)
#   ./tasks.sh build            # build all artifacts
#   ./tasks.sh clean            # remove build/test artifacts
#   ./tasks.sh help             # list all commands
#
# Note: Linux is a v1.1 target. This script is provided so contributors on
# Linux/macOS can develop and run tests, but Windows-specific functionality
# (Windows Services, Task Scheduler, Job Objects, WDAC) will be stubbed.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Pick the right Python interpreter
if [[ -x ".venv/bin/python" ]]; then
    PY=(".venv/bin/python")
elif command -v python3 &> /dev/null; then
    PY=(python3)
else
    PY=(python)
fi

command="${1:-help}"
shift || true

case "$command" in
    help|--help|-h)
        cat <<'USAGE'
AAiOS task runner (bash)
Usage: ./tasks.sh <command>

Commands:
  dev                Start dev stack (API + Next.js)
  api                Start API server only
  web                Start Next.js dev server only
  test               Run all Python tests
  test-unit          Run unit tests only
  test-integration   Run integration tests only
  test-e2e           Run end-to-end tests
  test-web           Run web (Vitest) tests
  test-offline       Run tests with no network (mocked providers)
  lint               Ruff + mypy + bandit + eslint
  typecheck          TypeScript typecheck (web)
  format             Ruff format + Prettier
  check              Lint + typecheck + test (run before pushing)
  build              Build wheel + Next.js build
  build-wheel        Build Python wheel only
  build-web          Build Next.js only
  docker-up          Start the optional Docker Compose stack
  docker-down        Stop the Docker Compose stack
  clean              Remove build/test artifacts
  venv               Create .venv with dev extras
  install            Install Python deps + pnpm install
  doctor             Run 'aaios doctor'
  version            Print AAiOS version
USAGE
        ;;

    venv)
        echo "==> Create virtual environment"
        python3 -m venv .venv
        ./.venv/bin/python -m pip install --upgrade pip
        ./.venv/bin/pip install -e ".[dev,linux]"
        echo "✓ Virtual environment created at .venv"
        ;;

    install)
        echo "==> Install Python dependencies"
        "${PY[@]}" -m pip install --upgrade pip
        "${PY[@]}" -m pip install -e ".[dev,linux]"
        echo "==> Install pnpm dependencies"
        pnpm install
        echo "✓ All dependencies installed"
        ;;

    dev)
        echo "==> Starting API server on http://127.0.0.1:8000 ..."
        echo "==> Starting Next.js dev server on http://127.0.0.1:3000 ..."
        echo "Press Ctrl+C to stop both."
        # Start API in background
        "${PY[@]}" -m uvicorn surfaces.api.app:app --reload --host 127.0.0.1 --port 8000 &
        api_pid=$!
        # Start web in background
        pnpm --filter '@aaios/web' dev &
        web_pid=$!
        # Trap Ctrl+C
        trap "kill $api_pid $web_pid 2>/dev/null || true" EXIT INT TERM
        wait $api_pid
        ;;

    api)
        "${PY[@]}" -m uvicorn surfaces.api.app:app --reload --host 127.0.0.1 --port 8000
        ;;

    web)
        pnpm --filter '@aaios/web' dev
        ;;

    test)
        "${PY[@]}" -m pytest
        ;;

    test-unit)
        "${PY[@]}" -m pytest tests/unit
        ;;

    test-integration)
        "${PY[@]}" -m pytest tests/integration
        ;;

    test-e2e)
        "${PY[@]}" -m pytest tests/e2e
        ;;

    test-web)
        pnpm --filter '@aaios/web' test
        ;;

    test-offline)
        "${PY[@]}" -m pytest -m offline
        ;;

    lint)
        echo "==> Ruff (lint)"
        "${PY[@]}" -m ruff check .
        echo "==> Ruff (format check)"
        "${PY[@]}" -m ruff format --check .
        echo "==> Mypy"
        "${PY[@]}" -m mypy
        echo "==> Bandit"
        "${PY[@]}" -m bandit -c pyproject.toml -r core services agents supervisor orchestrator surfaces/api surfaces/cli
        echo "==> ESLint (web)"
        pnpm --filter '@aaios/web' lint
        ;;

    typecheck)
        echo "==> TypeScript typecheck (web)"
        pnpm --filter '@aaios/web' typecheck
        ;;

    format)
        echo "==> Ruff format"
        "${PY[@]}" -m ruff format .
        echo "==> Ruff fix"
        "${PY[@]}" -m ruff check --fix .
        echo "==> Prettier"
        pnpm exec prettier --write .
        ;;

    check)
        ./tasks.sh lint
        ./tasks.sh typecheck
        ./tasks.sh test
        echo ""
        echo "✓ All checks passed"
        ;;

    build)
        ./tasks.sh build-wheel
        ./tasks.sh build-web
        ;;

    build-wheel)
        echo "==> Build Python wheel"
        "${PY[@]}" -m pip install --upgrade hatch
        "${PY[@]}" -m hatch build
        ;;

    build-web)
        echo "==> Build Next.js"
        pnpm --filter '@aaios/web' build
        ;;

    docker-up)
        echo "==> Start Docker Compose stack"
        docker compose -f deploy/docker/docker-compose.yml up -d
        ;;

    docker-down)
        echo "==> Stop Docker Compose stack"
        docker compose -f deploy/docker/docker-compose.yml down
        ;;

    clean)
        echo "==> Remove build/test artifacts"
        rm -rf .mypy_cache .ruff_cache .pytest_cache coverage build dist
        rm -rf surfaces/web/.next surfaces/web/out surfaces/web/coverage surfaces/web/test-results
        find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
        echo "✓ Cleaned"
        ;;

    doctor)
        "${PY[@]}" -m surfaces.cli doctor
        ;;

    version)
        "${PY[@]}" -m surfaces.cli version
        ;;

    *)
        echo "Unknown command: $command" >&2
        echo "Run './tasks.sh help' for the list of commands." >&2
        exit 1
        ;;
esac
