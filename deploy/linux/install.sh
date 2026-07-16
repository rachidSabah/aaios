#!/usr/bin/env bash
# AAiOS v5.3.2 — One-click installer for Linux / WSL2 / macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/linux/install.sh | bash
#
# Or with options:
#   curl -fsSL ... | bash -s -- --mode silent --workspace /opt/aaios
#
# Supported modes: interactive silent minimal developer enterprise portable offline repair force upgrade validate

set -euo pipefail

REPO_URL="https://github.com/rachidSabah/aaios.git"
DEFAULT_WORKSPACE="${HOME}/.aaios"
MODE="interactive"
WORKSPACE=""
PROFILE=""
FORCE=""

# Color helpers
if [ -t 1 ]; then
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    CYAN=''; GREEN=''; YELLOW=''; RED=''; NC=''
fi

log_step() { echo -e "${CYAN}==> $1${NC}"; }
log_ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
log_warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
log_err()  { echo -e "  ${RED}✗ $1${NC}" >&2; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)      MODE="$2"; shift 2 ;;
        --workspace) WORKSPACE="$2"; shift 2 ;;
        --profile)   PROFILE="$2"; shift 2 ;;
        --force)     FORCE="--force"; shift ;;
        --interactive|--silent|--minimal|--developer|--enterprise|--portable|--offline|--repair|--upgrade|--validate)
            MODE="${1#--}"; shift ;;
        -h|--help)
            cat <<EOF
AAiOS Installer

Usage: install.sh [OPTIONS]

Options:
  --mode MODE         Installation mode (default: interactive)
  --workspace PATH    Workspace root path
  --profile PROFILE   Configuration profile
  --force             Force installation past blockers
  --interactive       Shortcut for --mode=interactive
  --silent            Shortcut for --mode=silent
  --minimal           Shortcut for --mode=minimal
  --developer         Shortcut for --mode=developer
  --enterprise        Shortcut for --mode=enterprise
  --portable          Shortcut for --mode=portable
  --offline           Shortcut for --mode=offline
  --repair            Shortcut for --mode=repair
  --upgrade           Shortcut for --mode=upgrade
  --validate          Shortcut for --mode=validate
  -h, --help          Show this help

Modes:
  interactive  Prompt for each choice (default)
  silent       No prompts, apply defaults
  minimal      Only required subsystems
  developer    Development profile with debug logging
  enterprise   Strict production profile
  portable     Self-contained, no system services
  offline      No network operations
  repair       Repair an existing installation
  force        Force past compatibility blockers
  upgrade      Upgrade in place
  validate     Validate an existing installation
EOF
            exit 0 ;;
        *) log_err "Unknown option: $1"; exit 1 ;;
    esac
done

# Detect platform
detect_platform() {
    local os_name os_version
    os_name="$(uname -s | tr '[:upper:]' '[:lower:]')"
    os_version="$(uname -r)"
    if [ "$os_name" = "linux" ] && grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
        log_ok "Platform: WSL2 (Linux $os_version)"
        return 0
    elif [ "$os_name" = "linux" ]; then
        log_ok "Platform: Linux ($os_version)"
        return 0
    elif [ "$os_name" = "darwin" ]; then
        log_warn "Platform: macOS (experimental)"
        return 0
    else
        log_err "Unsupported platform: $os_name"
        return 1
    fi
}

# Check Python
check_python() {
    log_step "Checking Python..."
    if command -v python3 >/dev/null 2>&1; then
        local py_ver
        py_ver="$(python3 --version 2>&1 | awk '{print $2}')"
        local py_major py_minor
        py_major="${py_ver%%.*}"
        py_minor="${py_ver#*.}"
        py_minor="${py_minor%%.*}"
        if [ "$py_major" -ge 3 ] && [ "$py_minor" -ge 12 ]; then
            log_ok "Python $py_ver"
            return 0
        fi
        log_warn "Python $py_ver found (3.12+ required)"
    else
        log_warn "Python 3 not found"
    fi
    # Try to install
    if command -v apt-get >/dev/null 2>&1; then
        log_step "Installing Python 3.12 via apt..."
        sudo apt-get update -qq && sudo apt-get install -y -qq python3.12 python3.12-venv python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        log_step "Installing Python 3 via dnf..."
        sudo dnf install -y python3 python3-pip
    elif command -v brew >/dev/null 2>&1; then
        log_step "Installing Python 3.12 via brew..."
        brew install python@3.12
    else
        log_err "Cannot install Python automatically — please install Python 3.12+ manually"
        return 1
    fi
}

# Check Git
check_git() {
    log_step "Checking Git..."
    if command -v git >/dev/null 2>&1; then
        log_ok "Git $(git --version | awk '{print $3}')"
        return 0
    fi
    log_warn "Git not found — attempting to install"
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get install -y -qq git
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y git
    elif command -v brew >/dev/null 2>&1; then
        brew install git
    else
        log_err "Cannot install Git automatically"
        return 1
    fi
}

# Clone AAiOS
clone_aaios() {
    local target="$1"
    log_step "Cloning AAiOS to $target..."
    if [ -d "$target/.git" ]; then
        log_ok "Repository already exists — pulling latest"
        git -C "$target" fetch --quiet origin
        git -C "$target" checkout main --quiet 2>/dev/null || true
        git -C "$target" pull --quiet origin main
    else
        git clone --depth 1 --branch main "$REPO_URL" "$target"
        log_ok "Cloned AAiOS"
    fi
}

# Create virtual environment
create_venv() {
    local target="$1"
    log_step "Creating Python virtual environment..."
    if [ ! -d "$target/.venv" ]; then
        python3 -m venv "$target/.venv"
        log_ok "Virtual environment created"
    else
        log_ok "Virtual environment already exists"
    fi
    # Install package
    "$target/.venv/bin/pip" install --quiet --upgrade pip
    "$target/.venv/bin/pip" install --quiet -e "$target"
    log_ok "AAiOS package installed"
}

# Run the installer
run_installer() {
    local target="$1"
    log_step "Running AAiOS installer (mode: $MODE)..."
    local args=(
        "install" "--mode" "$MODE"
    )
    if [ -n "$WORKSPACE" ]; then
        args+=("--workspace" "$WORKSPACE")
    fi
    if [ -n "$PROFILE" ]; then
        args+=("--profile" "$PROFILE")
    fi
    if [ -n "$FORCE" ]; then
        args+=("$FORCE")
    fi
    "$target/.venv/bin/python" -m surfaces.cli "${args[@]}"
}

# Main
main() {
    echo -e "${CYAN}AAiOS v5.3.2 Installer${NC}"
    echo ""

    detect_platform || exit 1
    check_python || exit 1
    check_git || exit 1

    # Determine install target
    if [ -z "$WORKSPACE" ]; then
        WORKSPACE="$DEFAULT_WORKSPACE"
    fi

    # Clone into a temp location for the source, then install into the workspace
    local source_dir="${HOME}/.aaios-src"
    mkdir -p "$source_dir"
    clone_aaios "$source_dir"
    create_venv "$source_dir"
    run_installer "$source_dir"

    echo ""
    log_ok "AAiOS installation complete!"
    echo ""
    echo -e "  ${CYAN}Workspace:${NC}  $WORKSPACE"
    echo -e "  ${CYAN}Source:${NC}     $source_dir"
    echo -e "  ${CYAN}CLI:${NC}        $source_dir/.venv/bin/aaios"
    echo ""
    echo "Next steps:"
    echo "  1. Add the CLI to your PATH:"
    echo "     export PATH=\"$source_dir/.venv/bin:\$PATH\""
    echo "  2. Verify the installation:"
    echo "     aaios doctor"
    echo "  3. Start the dashboard:"
    echo "     aaios dev"
}

main "$@"
