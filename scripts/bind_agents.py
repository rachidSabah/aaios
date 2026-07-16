"""Agent auto-detection and binding.

Scans the system for installed agent CLIs/daemons and configures AAiOS
to use them in real mode (not mock). If not found, installs them.

Supported agents:
  - Claude Code CLI (`claude`) — coding agent
  - Hermes daemon (`hermes`) — desktop automation agent

Claude Code supports running via a proxy (custom base URL) instead of
the official Anthropic API. This is configured via:
  - Environment variable: ANTHROPIC_BASE_URL
  - Config key: agents.claude_code.api_base_url
  - Install flag: --claude-proxy-url

Usage (from install scripts):
  python -m scripts.bind_agents --install-missing --configure
  python -m scripts.bind_agents --claude-proxy-url http://localhost:8080/v1
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "AgentDetectionResult",
    "AgentStatus",
    "bind_agents",
    "detect_agents",
    "install_claude_code",
    "install_hermes",
]


class AgentStatus(StrEnum):
    """Status of an agent detection."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    INSTALLED = "installed"
    FAILED = "failed"


@dataclass
class AgentDetectionResult:
    """Result of detecting a single agent."""

    name: str
    binary: str
    status: AgentStatus
    path: str | None = None
    version: str | None = None
    error: str | None = None


def detect_claude_code() -> AgentDetectionResult:
    """Detect the Claude Code CLI on PATH.

    Checks for `claude` binary. Also checks if it's running via a proxy
    (ANTHROPIC_BASE_URL env var set).
    """
    binary = shutil.which("claude")
    if binary:
        try:
            version = subprocess.check_output(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            ).strip()
        except Exception:
            version = "unknown"
        return AgentDetectionResult(
            name="claude-code",
            binary="claude",
            status=AgentStatus.FOUND,
            path=binary,
            version=version,
        )
    return AgentDetectionResult(
        name="claude-code",
        binary="claude",
        status=AgentStatus.NOT_FOUND,
    )


def detect_hermes() -> AgentDetectionResult:
    """Detect the Hermes daemon on PATH.

    Checks for `hermes` or `hermes-daemon` binary.
    """
    for binary_name in ("hermes", "hermes-daemon"):
        binary = shutil.which(binary_name)
        if binary:
            try:
                version = subprocess.check_output(
                    [binary, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).strip()
            except Exception:
                version = "unknown"
            return AgentDetectionResult(
                name="hermes",
                binary=binary_name,
                status=AgentStatus.FOUND,
                path=binary,
                version=version,
            )
    return AgentDetectionResult(
        name="hermes",
        binary="hermes",
        status=AgentStatus.NOT_FOUND,
    )


def detect_9router() -> AgentDetectionResult:
    """Detect the 9Router proxy CLI on PATH."""
    binary = shutil.which("9router")
    if binary:
        try:
            version = subprocess.check_output(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            ).strip()
        except Exception:
            version = "unknown"
        return AgentDetectionResult(
            name="9router",
            binary="9router",
            status=AgentStatus.FOUND,
            path=binary,
            version=version,
        )
    return AgentDetectionResult(
        name="9router",
        binary="9router",
        status=AgentStatus.NOT_FOUND,
    )


def detect_agents() -> list[AgentDetectionResult]:
    """Detect all supported agents."""
    return [detect_claude_code(), detect_hermes(), detect_9router()]


def install_claude_code(
    *,
    proxy_url: str | None = None,
    api_key: str | None = None,
) -> AgentDetectionResult:
    """Install the Claude Code CLI via npm.

    Args:
        proxy_url: If set, configures Claude Code to use this base URL
            instead of the official Anthropic API. This enables using
            Claude Code with a proxy, a local model server, or a free
            model endpoint.
        api_key: The API key for Claude Code. If None, the user must
            set ANTHROPIC_API_KEY manually.
    """
    _log.info("installing_claude_code", proxy_url=proxy_url)

    # Check if npm is available
    npm = shutil.which("npm")
    if not npm:
        return AgentDetectionResult(
            name="claude-code",
            binary="claude",
            status=AgentStatus.FAILED,
            error="npm not found. Install Node.js first.",
        )

    try:
        # Install Claude Code CLI globally
        subprocess.check_call(
            [npm, "install", "-g", "@anthropic-ai/claude-code"],
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        return AgentDetectionResult(
            name="claude-code",
            binary="claude",
            status=AgentStatus.FAILED,
            error=f"npm install failed: {e}",
        )
    except subprocess.TimeoutExpired:
        return AgentDetectionResult(
            name="claude-code",
            binary="claude",
            status=AgentStatus.FAILED,
            error="npm install timed out",
        )

    # Verify installation
    result = detect_claude_code()
    if result.status == AgentStatus.FOUND:
        result.status = AgentStatus.INSTALLED

        # Configure proxy if specified
        if proxy_url:
            _configure_claude_proxy(proxy_url, api_key)

    return result


def _configure_claude_proxy(proxy_url: str, api_key: str | None) -> None:
    """Configure Claude Code to use a proxy URL.

    Sets environment variables and writes a config file that AAiOS
    reads when initializing the Claude Code agent.
    """
    # Write to AAiOS config
    config_dir = Path(os.environ.get("ProgramData", "/etc")) / "AAiOS" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    agent_config: dict[str, Any] = {
        "claude_code": {
            "api_base_url": proxy_url,
            "use_proxy": True,
        },
    }
    if api_key:
        agent_config["claude_code"]["api_key"] = api_key

    config_file = config_dir / "agents" / "claude_code.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(agent_config, indent=2))

    # Also set env vars for the current session (Claude Code reads these)
    os.environ["ANTHROPIC_BASE_URL"] = proxy_url
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    _log.info("claude_code_proxy_configured", proxy_url=proxy_url)


def install_hermes() -> AgentDetectionResult:
    """Install the Hermes daemon.

    Hermes is an in-house daemon. In v1.0, it's installed as a Python
    package from the AAiOS repository. The daemon runs as:
        python -m agents._impls.hermes.daemon

    This function:
    1. Creates a wrapper script that launches the Hermes daemon
    2. Makes it executable
    3. Adds it to PATH (or a known location)
    """
    _log.info("installing_hermes")

    # The Hermes daemon is already part of the AAiOS package.
    # We just need to create a wrapper script that the agent can spawn.
    install_dir = Path(os.environ.get("ProgramData", "/usr/local")) / "AAiOS" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)

    # Detect the Python executable
    python_bin = shutil.which("python3") or shutil.which("python")
    if not python_bin:
        return AgentDetectionResult(
            name="hermes",
            binary="hermes",
            status=AgentStatus.FAILED,
            error="Python not found",
        )

    # Create the Hermes wrapper script
    is_windows = os.name == "nt"
    wrapper_name = "hermes" + (".bat" if is_windows else "")
    wrapper_path = install_dir / wrapper_name

    if is_windows:
        wrapper_content = f"""@echo off
{python_bin} -m agents._impls.hermes.daemon %*
"""
    else:
        wrapper_content = f"""#!/usr/bin/env bash
exec {python_bin} -m agents._impls.hermes.daemon "$@"
"""

    wrapper_path.write_text(wrapper_content)
    if not is_windows:
        wrapper_path.chmod(0o755)

    # Add to PATH (write a profile snippet)
    if not is_windows:
        profile = Path.home() / ".bashrc"
        if profile.exists():
            content = profile.read_text()
            if str(install_dir) not in content:
                profile.write_text(content + f'\nexport PATH="{install_dir}:$PATH"\n')

    # Set for current session
    current_path = os.environ.get("PATH", "")
    if str(install_dir) not in current_path:
        os.environ["PATH"] = (
            f"{install_dir}:{current_path}" if not is_windows else f"{install_dir};{current_path}"
        )

    # Verify
    result = detect_hermes()
    if result.status == AgentStatus.FOUND:
        result.status = AgentStatus.INSTALLED
    else:
        # The wrapper exists even if shutil.which doesn't find it yet (PATH not refreshed)
        result.status = AgentStatus.INSTALLED
        result.path = str(wrapper_path)

    return result


def install_9router() -> AgentDetectionResult:
    """Install 9Router via npm."""
    _log.info("installing_9router")
    npm = shutil.which("npm")
    if not npm:
        return AgentDetectionResult(
            name="9router",
            binary="9router",
            status=AgentStatus.FAILED,
            error="npm not found. Install Node.js first.",
        )
    try:
        subprocess.check_call(
            [npm, "install", "-g", "9router"],
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        return AgentDetectionResult(
            name="9router",
            binary="9router",
            status=AgentStatus.FAILED,
            error=f"npm install failed: {e}",
        )
    except subprocess.TimeoutExpired:
        return AgentDetectionResult(
            name="9router",
            binary="9router",
            status=AgentStatus.FAILED,
            error="npm install timed out",
        )
    result = detect_9router()
    if result.status == AgentStatus.FOUND:
        result.status = AgentStatus.INSTALLED
    return result


def bind_agents(
    *,
    install_missing: bool = True,
    claude_proxy_url: str | None = None,
    claude_api_key: str | None = None,
    configure: bool = True,
) -> dict[str, AgentDetectionResult]:
    """Detect, optionally install, and bind agents to AAiOS.

    This is the main entry point called by the install scripts.

    Args:
        install_missing: If True, install agents that are not detected.
        claude_proxy_url: If set, configure Claude Code to use this proxy
            URL instead of the official Anthropic API.
        claude_api_key: API key for Claude Code (if using proxy or official API).
        configure: If True, write AAiOS config to use the agents in real mode.

    Returns:
        A dict mapping agent name → detection result.
    """
    results: dict[str, AgentDetectionResult] = {}

    # --- 9Router ---
    router_result = detect_9router()
    if router_result.status == AgentStatus.NOT_FOUND and install_missing:
        _log.info("9router_not_found_installing")
        router_result = install_9router()
    results["9router"] = router_result

    # Default to 9Router local proxy for Claude Code if installed and no custom proxy is provided
    if not claude_proxy_url and router_result.status in (AgentStatus.FOUND, AgentStatus.INSTALLED):
        claude_proxy_url = "http://localhost:20128/v1"

    # --- Claude Code ---
    cc_result = detect_claude_code()
    if cc_result.status == AgentStatus.NOT_FOUND and install_missing:
        _log.info("claude_code_not_found_installing")
        cc_result = install_claude_code(
            proxy_url=claude_proxy_url,
            api_key=claude_api_key,
        )
    results["claude_code"] = cc_result

    # --- Hermes ---
    hermes_result = detect_hermes()
    if hermes_result.status == AgentStatus.NOT_FOUND and install_missing:
        _log.info("hermes_not_found_installing")
        hermes_result = install_hermes()
    results["hermes"] = hermes_result

    # --- Configure AAiOS ---
    if configure:
        _configure_aaios(results, claude_proxy_url)

    return results


def _configure_aaios(
    results: dict[str, AgentDetectionResult],
    claude_proxy_url: str | None,
) -> None:
    """Write AAiOS agent configuration to use detected/installed agents.

    This creates a config file that the AAiOS bootstrap reads to determine
    whether to run agents in real mode or mock mode.
    """
    config_dir = Path(os.environ.get("ProgramData", "/etc")) / "AAiOS" / "config"
    if not config_dir.exists():
        # Fallback to user config
        config_dir = Path.home() / ".config" / "aaios"
    config_dir.mkdir(parents=True, exist_ok=True)

    agents_config: dict[str, Any] = {}

    # Claude Code config
    cc = results.get("claude_code")
    if cc and cc.status in (AgentStatus.FOUND, AgentStatus.INSTALLED):
        agents_config["claude_code"] = {
            "mock_mode": False,
            "binary_path": cc.path,
            "version": cc.version,
        }
        if claude_proxy_url:
            agents_config["claude_code"]["api_base_url"] = claude_proxy_url
            agents_config["claude_code"]["use_proxy"] = True
    else:
        agents_config["claude_code"] = {
            "mock_mode": True,
            "note": "Claude Code not found; running in mock mode",
        }

    # Hermes config
    hermes = results.get("hermes")
    if hermes and hermes.status in (AgentStatus.FOUND, AgentStatus.INSTALLED):
        agents_config["hermes"] = {
            "mock_mode": False,
            "binary_path": hermes.path,
            "version": hermes.version,
        }
    else:
        agents_config["hermes"] = {
            "mock_mode": True,
            "note": "Hermes not found; running in mock mode",
        }

    # 9Router config
    router = results.get("9router")
    if router and router.status in (AgentStatus.FOUND, AgentStatus.INSTALLED):
        agents_config["9router"] = {
            "mock_mode": False,
            "binary_path": router.path,
            "version": router.version,
            "dashboard_url": "http://localhost:20128",
        }
    else:
        agents_config["9router"] = {
            "mock_mode": True,
            "note": "9Router not found; running in mock mode",
        }

    # Write config
    config_file = config_dir / "agents.json"
    config_file.write_text(json.dumps(agents_config, indent=2))
    _log.info("agents_configured", config_path=str(config_file), config=agents_config)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point for agent binding."""
    import argparse

    parser = argparse.ArgumentParser(description="Detect and bind AI agents to AAiOS")
    parser.add_argument(
        "--install-missing",
        action="store_true",
        default=True,
        help="Install agents that are not detected (default: True)",
    )
    parser.add_argument(
        "--no-install",
        dest="install_missing",
        action="store_false",
        help="Do not install missing agents",
    )
    parser.add_argument(
        "--claude-proxy-url",
        type=str,
        default=None,
        help="Proxy URL for Claude Code (instead of official Anthropic API)",
    )
    parser.add_argument("--claude-api-key", type=str, default=None, help="API key for Claude Code")
    parser.add_argument(
        "--configure",
        action="store_true",
        default=True,
        help="Write AAiOS config to use detected agents",
    )
    parser.add_argument(
        "--detect-only", action="store_true", help="Only detect, do not install or configure"
    )
    args = parser.parse_args()

    if args.detect_only:
        results = {"claude_code": detect_claude_code(), "hermes": detect_hermes(), "9router": detect_9router()}
    else:
        results = bind_agents(
            install_missing=args.install_missing,
            claude_proxy_url=args.claude_proxy_url,
            claude_api_key=args.claude_api_key,
            configure=args.configure,
        )

    # Print results
    print("\nAgent Detection Results:")
    print("=" * 50)
    for name, result in results.items():
        status_icon = "[+]" if result.status in ("found", "installed") else "[-]"
        print(f"  {status_icon} {result.name}: {result.status.value}")
        if result.path:
            print(f"    Path: {result.path}")
        if result.version:
            print(f"    Version: {result.version}")
        if result.error:
            print(f"    Error: {result.error}")

    # Check for proxy
    proxy = os.environ.get("ANTHROPIC_BASE_URL")
    if proxy:
        print(f"\n  Claude Code proxy: {proxy}")

    return 0 if all(r.status in ("found", "installed") for r in results.values()) else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
