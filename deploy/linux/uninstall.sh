#!/usr/bin/env bash
# ============================================================================
# AAiOS One-Click Uninstaller for Linux
# ============================================================================
# Fully removes AAiOS: stops processes, removes venv, deletes data/config/logs,
# uninstalls npm packages (claude-code), and cleans up.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/linux/uninstall.sh | bash
#
# With options:
#   curl -fsSL ... | bash -s -- --remove-data --remove-agents
# ============================================================================

set -euo pipefail

INSTALL_DIR="${HOME}/aaios"
REMOVE_DATA=false
REMOVE_AGENTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --remove-data) REMOVE_DATA=true; shift ;;
        --remove-agents) REMOVE_AGENTS=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; NC='\033[0m'
step() { echo -e "\n${CYAN}==> $1${NC}"; }
ok() { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }

echo -e "${MAGENTA}╔══════════════════════════════════════════════════╗"
echo -e "║       AAiOS One-Click Uninstaller v1.0.0         ║"
echo -e "╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Install dir: $INSTALL_DIR"
echo "Remove data: $REMOVE_DATA"
echo "Remove agents: $REMOVE_AGENTS"
echo ""

# --- Step 1: Stop running processes ---
step "Stopping AAiOS processes..."
pkill -f "scripts/start.py" 2>/dev/null && ok "Stopped start.py" || ok "No start.py running"
pkill -f "uvicorn surfaces.api" 2>/dev/null && ok "Stopped API server" || ok "No API server running"
pkill -f "supervisor.runtime" 2>/dev/null && ok "Stopped supervisor" || ok "No supervisor running"
pkill -f "hermes" 2>/dev/null && ok "Stopped Hermes" || ok "No Hermes running"

# --- Step 2: Remove Python venv ---
step "Removing Python environment..."
if [ -d "$INSTALL_DIR/.venv" ]; then
    rm -rf "$INSTALL_DIR/.venv"
    ok "Virtual environment removed"
else
    ok "No virtual environment found"
fi

# Uninstall pip package
pip uninstall -y aaios 2>/dev/null && ok "pip package uninstalled" || ok "pip package not installed"

# --- Step 3: Remove Node.js packages ---
step "Removing Node.js packages..."
if [ -d "$INSTALL_DIR/node_modules" ]; then
    rm -rf "$INSTALL_DIR/node_modules"
    ok "node_modules removed"
else
    ok "No node_modules found"
fi

# --- Step 4: Optionally remove agent CLIs ---
if [ "$REMOVE_AGENTS" = true ]; then
    step "Removing AI agent CLIs..."
    if command -v claude &>/dev/null; then
        npm uninstall -g @anthropic-ai/claude-code 2>/dev/null && ok "Claude Code CLI uninstalled" || warn "Could not uninstall Claude Code"
    else
        ok "Claude Code CLI not found"
    fi
    # Remove Hermes wrapper
    for dir in /usr/local/AAiOS/bin /usr/local/bin; do
        [ -f "$dir/hermes" ] && rm -f "$dir/hermes" && ok "Removed Hermes wrapper at $dir/hermes"
    done
else
    warn "Skipping agent CLI removal (use --remove-agents to remove them)"
fi

# --- Step 5: Remove config/data/logs ---
step "Removing configuration and data..."
CONFIG_DIR="${HOME}/.config/aaios"
DATA_DIR="${HOME}/.local/share/aaios"

if [ -d "$CONFIG_DIR" ]; then
    if [ "$REMOVE_DATA" = true ]; then
        rm -rf "$CONFIG_DIR"
        ok "Removed $CONFIG_DIR"
    else
        warn "Keeping $CONFIG_DIR (use --remove-data to delete)"
    fi
fi

if [ -d "$DATA_DIR" ]; then
    if [ "$REMOVE_DATA" = true ]; then
        rm -rf "$DATA_DIR"
        ok "Removed $DATA_DIR"
    else
        warn "Keeping $DATA_DIR (use --remove-data to delete)"
    fi
fi

# Remove from /etc if exists (system-wide)
if [ -d "/etc/aaios" ]; then
    sudo rm -rf /etc/aaios 2>/dev/null && ok "Removed /etc/aaios" || warn "Could not remove /etc/aaios (need sudo)"
fi

# Remove temp
rm -rf /tmp/aaios 2>/dev/null && ok "Removed /tmp/aaios" || true

# --- Step 6: Remove the repository ---
step "Removing AAiOS repository..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    if [ -d "$INSTALL_DIR" ]; then
        warn "Could not remove $INSTALL_DIR (may be in use). Close all terminals and retry."
    else
        ok "Repository removed"
    fi
else
    ok "Repository not found"
fi

# --- Step 7: Clean PATH ---
step "Cleaning up..."
if [ -f "$HOME/.bashrc" ]; then
    sed -i '/AAiOS/d' "$HOME/.bashrc" 2>/dev/null
    ok "Cleaned .bashrc"
fi
if [ -f "$HOME/.zshrc" ]; then
    sed -i '/AAiOS/d' "$HOME/.zshrc" 2>/dev/null
    ok "Cleaned .zshrc"
fi

# --- Done ---
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║          Uninstallation Complete!                ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  AAiOS has been fully removed.                   ║"
echo "║                                                  ║"
echo "║  System dependencies (Python, Node.js, git)      ║"
echo "║  were NOT removed.                               ║"
echo "║                                                  ║"
echo "║  To reinstall:                                   ║"
echo "║  curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/linux/uninstall.sh | bash"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
