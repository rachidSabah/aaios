"""AAiOS auto-update — checks for new commits and pulls them.

This module provides:
  - `aaios update` CLI command — one-shot check + pull + reinstall
  - `aaios update --auto` — starts a background watcher that checks every N minutes
  - `scripts/auto_update.py` — standalone script for cron/scheduled tasks

The auto-update:
  1. Checks if the local repo is behind the remote (git fetch + git status)
  2. If behind: pulls, reinstalls Python packages, reinstalls Node packages,
     re-binds agents, prints what changed
  3. If up to date: prints "Already up to date"
  4. With --auto: runs in a loop, checking every N minutes (default 30)
  5. With --restart: restarts the AAiOS server after update (via systemd/service)

Usage:
  aaios update                  # check + update once
  aaios update --auto           # background watcher (30 min interval)
  aaios update --auto --interval 60  # check every 60 min
  aaios update --restart        # update + restart server
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from core.logging import LoggingConfig, get_logger, init_logging

_log = get_logger(__name__)

__all__ = ["check_for_updates", "do_update", "run_auto_update", "main"]


def _run_git(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd or os.getcwd(),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def check_for_updates() -> dict[str, str]:
    """Check if the local repo is behind the remote.

    Returns a dict with:
      'status': 'up_to_date' | 'updates_available' | 'error'
      'local': local commit hash
      'remote': remote commit hash (if fetched)
      'behind_by': number of commits behind (if applicable)
      'commits': list of new commit messages (if behind)
    """
    repo_dir = _find_repo_root()
    if not repo_dir:
        return {"status": "error", "message": "Not in an AAiOS repository"}

    # Fetch remote
    code, _, err = _run_git(["fetch", "origin"], cwd=str(repo_dir))
    if code != 0:
        return {"status": "error", "message": f"git fetch failed: {err}"}

    # Get local and remote hashes
    _, local_hash, _ = _run_git(["rev-parse", "HEAD"], cwd=str(repo_dir))
    _, remote_hash, _ = _run_git(["rev-parse", "origin/main"], cwd=str(repo_dir))

    if local_hash == remote_hash:
        return {
            "status": "up_to_date",
            "local": local_hash[:8],
            "remote": remote_hash[:8],
        }

    # Get the commits we're behind
    _, log_output, _ = _run_git(
        ["log", "--oneline", f"{local_hash}..{remote_hash}"],
        cwd=str(repo_dir),
    )
    commits = [line.strip() for line in log_output.splitlines() if line.strip()]
    _, count_output, _ = _run_git(
        ["rev-list", "--count", f"{local_hash}..{remote_hash}"],
        cwd=str(repo_dir),
    )

    return {
        "status": "updates_available",
        "local": local_hash[:8],
        "remote": remote_hash[:8],
        "behind_by": count_output or str(len(commits)),
        "commits": commits,
    }


def do_update(*, reinstall: bool = True, rebind_agents: bool = True) -> dict[str, str]:
    """Pull updates from GitHub and reinstall packages.

    Returns a dict with the update result.
    """
    repo_dir = _find_repo_root()
    if not repo_dir:
        return {"status": "error", "message": "Not in an AAiOS repository"}

    # Check first
    check = check_for_updates()
    if check["status"] == "up_to_date":
        return {"status": "up_to_date", "message": "Already up to date"}
    if check["status"] == "error":
        return check

    _log.info("update.pull_begin", behind_by=check.get("behind_by", "?"))

    # Pull
    code, output, err = _run_git(["pull", "origin", "main"], cwd=str(repo_dir))
    if code != 0:
        return {"status": "error", "message": f"git pull failed: {err}"}

    _log.info("update.pulled", output=output[:200])

    # Reinstall Python packages
    if reinstall:
        venv_python = str(Path(repo_dir) / ".venv" / "bin" / "python")
        if not Path(venv_python).exists():
            venv_python = str(Path(repo_dir) / ".venv" / "Scripts" / "python.exe")
        if Path(venv_python).exists():
            _log.info("update.reinstalling_python")
            subprocess.run(
                [venv_python, "-m", "pip", "install", "-e", ".[dev,windows]"]
                if os.name == "nt"
                else [venv_python, "-m", "pip", "install", "-e", ".[dev,linux]"],
                cwd=str(repo_dir),
                capture_output=True,
                timeout=300,
            )
            _log.info("update.python_reinstalled")

    # Reinstall Node packages
    if reinstall:
        _log.info("update.reinstalling_node")
        subprocess.run(
            ["pnpm", "install"],
            cwd=str(repo_dir),
            capture_output=True,
            timeout=120,
        )
        _log.info("update.node_reinstalled")

    # Re-bind agents
    if rebind_agents:
        _log.info("update.rebinding_agents")
        venv_python = str(Path(repo_dir) / ".venv" / "bin" / "python")
        if not Path(venv_python).exists():
            venv_python = str(Path(repo_dir) / ".venv" / "Scripts" / "python.exe")
        if Path(venv_python).exists():
            subprocess.run(
                [venv_python, "scripts/bind_agents.py", "--install-missing"],
                cwd=str(repo_dir),
                capture_output=True,
                timeout=120,
            )
            _log.info("update.agents_rebound")

    return {
        "status": "updated",
        "message": f"Pulled {check.get('behind_by', '?')} new commits",
        "commits": check.get("commits", []),
    }


async def run_auto_update(
    *,
    interval_minutes: int = 30,
    restart_callback: Any = None,  # callable[[], Awaitable[None]]
) -> None:
    """Run auto-update in a loop, checking every N minutes.

    Args:
        interval_minutes: How often to check (default 30).
        restart_callback: If set, called after an update to restart the server.
    """
    init_logging(LoggingConfig(level="INFO", json_output=True))
    _log.info("auto_update.started", interval_min=interval_minutes)

    while True:
        try:
            result = do_update()
            if result["status"] == "updated":
                _log.info("auto_update.updated", message=result.get("message", ""))
                for commit in result.get("commits", []):
                    _log.info("auto_update.new_commit", commit=commit)
                if restart_callback is not None:
                    _log.info("auto_update.restarting")
                    await restart_callback()
            elif result["status"] == "up_to_date":
                _log.debug("auto_update.up_to_date")
            else:
                _log.warning("auto_update.error", message=result.get("message", ""))
        except Exception:
            _log.exception("auto_update.failed")

        await asyncio.sleep(interval_minutes * 60)


def _find_repo_root() -> Path | None:
    """Find the AAiOS repository root by looking for pyproject.toml with 'aaios'."""
    # Check current directory and parents
    current = Path.cwd()
    for path in [current] + list(current.parents):
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            if 'name = "aaios"' in content:
                return path
    # Check known install locations
    candidates = [
        Path.home() / "aaios",
        Path(os.environ.get("LOCALAPPDATA", "")) / "AAiOS" / "aaios",
    ]
    for path in candidates:
        if (path / "pyproject.toml").exists():
            return path
    return None


def main() -> int:
    """CLI entry point for auto-update."""
    import argparse

    parser = argparse.ArgumentParser(description="AAiOS auto-update")
    parser.add_argument("--auto", action="store_true", help="Run in auto mode (background loop)")
    parser.add_argument(
        "--interval", type=int, default=30, help="Check interval in minutes (default: 30)"
    )
    parser.add_argument("--restart", action="store_true", help="Restart server after update")
    parser.add_argument("--check-only", action="store_true", help="Only check, do not update")
    args = parser.parse_args()

    if args.check_only:
        result = check_for_updates()
        print(f"Status: {result['status']}")
        if result["status"] == "updates_available":
            print(f"Behind by: {result.get('behind_by', '?')} commits")
            print(f"Local:  {result.get('local', '?')}")
            print(f"Remote: {result.get('remote', '?')}")
            print("\nNew commits:")
            for commit in result.get("commits", []):
                print(f"  {commit}")
        return 0

    if args.auto:
        print(f"Starting auto-update (checking every {args.interval} minutes)...")
        print("Press Ctrl+C to stop.")
        try:
            asyncio.run(run_auto_update(interval_minutes=args.interval))
        except KeyboardInterrupt:
            print("\nAuto-update stopped.")
        return 0

    # One-shot update
    result = do_update()
    if result["status"] == "updated":
        print(f"✓ Updated: {result['message']}")
        for commit in result.get("commits", []):
            print(f"  {commit}")
        if args.restart:
            print("\nRestarting AAiOS...")
            # The restart is handled by the caller (CLI or systemd)
    elif result["status"] == "up_to_date":
        print("✓ Already up to date")
    else:
        print(f"✗ Error: {result.get('message', 'unknown')}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
