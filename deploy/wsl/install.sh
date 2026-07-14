#!/usr/bin/env bash
# ============================================================================
# AAiOS One-Click Installer for WSL (Windows Subsystem for Linux)
# ============================================================================
# Installs AAiOS with all dependencies on WSL2 (Ubuntu/Debian).
#
# Usage (one-line):
#   curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/wsl/install.sh | bash
#
# Or with options:
#   curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/wsl/install.sh | bash -s -- --install-dir ~/aaios --skip-deps
# ============================================================================

set -euo pipefail

REPO_URL="https://github.com/rachidSabah/aaios.git"
INSTALL_DIR="${HOME}/aaios"
SKIP_DEPS=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --skip-deps) SKIP_DEPS=true; shift ;;
        --force) FORCE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; NC='\033[0m'
step() { echo -e "\n${CYAN}==> $1${NC}"; }
ok() { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
err() { echo -e "  ${RED}✗ $1${NC}"; }

echo -e "${MAGENTA}╔══════════════════════════════════════════════════╗"
echo -e "║      AAiOS One-Click Installer v1.0.0 (WSL)     ║"
echo -e "║   Agentic AI Operating System — WSL2/Linux      ║"
echo -e "╚══════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$SKIP_DEPS" = false ]; then
    step "Installing system dependencies..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3 python3-venv python3-pip curl git build-essential libssl-dev libffi-dev 2>/dev/null
        ok "System packages installed (apt)"
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-devel curl git gcc make openssl-devel libffi-devel
        ok "System packages installed (dnf)"
    else
        warn "Unsupported package manager. Install Python 3.12+, Node.js 22, git manually."
    fi

    step "Checking Python..."
    PY=$(command -v python3.12 || command -v python3)
    if [ -z "$PY" ]; then err "Python 3 not found"; exit 1; fi
    ok "Python found: $($PY --version)"

    step "Checking Node.js..."
    if ! command -v node &>/dev/null; then
        warn "Node.js not found. Installing via NodeSource..."
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - 2>/dev/null || true
        sudo apt-get install -y -qq nodejs 2>/dev/null || warn "Install Node.js manually: https://nodejs.org/"
    else
        ok "Node.js found: $(node --version)"
    fi

    if ! command -v pnpm &>/dev/null; then
        warn "Installing pnpm..."; npm install -g pnpm 2>/dev/null || warn "Install pnpm manually"
    else
        ok "pnpm found"
    fi
fi

step "Cloning AAiOS..."
PARENT_DIR=$(dirname "$INSTALL_DIR"); mkdir -p "$PARENT_DIR"
if [ -d "$INSTALL_DIR" ]; then
    if [ "$FORCE" = true ]; then rm -rf "$INSTALL_DIR"; else
        ok "Updating existing..."; cd "$INSTALL_DIR"; git pull origin main; cd "$PARENT_DIR"
    fi
fi
[ ! -d "$INSTALL_DIR" ] && { cd "$PARENT_DIR"; git clone "$REPO_URL" "$(basename "$INSTALL_DIR")"; ok "Cloned"; }
cd "$INSTALL_DIR"

step "Python environment..."
[ ! -d ".venv" ] && $PY -m venv .venv && ok "venv created" || ok "venv exists"
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev,linux]" -q 2>/dev/null || pip install -e ".[dev]" -q
ok "Python packages installed"

step "Node.js environment..."
command -v pnpm &>/dev/null && { pnpm install 2>/dev/null; ok "Node packages installed"; } || warn "pnpm not available"

step "Configuration..."
CONFIG_DIR="${HOME}/.config/aaios"; DATA_DIR="${HOME}/.local/share/aaios"; LOG_DIR="${DATA_DIR}/logs"
mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
[ ! -f "$CONFIG_DIR/config.yaml" ] && cp config/defaults.yaml "$CONFIG_DIR/config.yaml" && ok "Config copied" || ok "Config exists"

step "Verifying..."
VERSION=$(python -m surfaces.cli version 2>&1); ok "AAiOS: $VERSION"
echo ""; echo -e "${YELLOW}Running doctor...${NC}"; python -m surfaces.cli doctor 2>&1 || true

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║            Installation Complete!                ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  Next steps:                                     ║"
echo "║  1. export OPENAI_API_KEY='sk-...'               ║"
echo "║  2. source .venv/bin/activate                    ║"
echo "║  3. python -m uvicorn surfaces.api.app:create_app --factory"
echo "║  4. Open http://127.0.0.1:8000/docs              ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "Repo:   $INSTALL_DIR"
echo "Config: $CONFIG_DIR/config.yaml"
