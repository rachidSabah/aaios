"""Execution domain handlers — one per execution domain.

Each handler implements the DomainHandler protocol:
  async def execute(request: ExecutionRequest) -> ExecutionResult

Handlers are responsible for:
  - Translating the action + parameters into real-world operations
  - Capturing stdout/stderr/exit codes
  - Recording resource usage
  - Creating rollback plans
  - Emitting logs

All handlers gracefully degrade when the underlying tool isn't available
(e.g., docker not installed → returns a clear error, doesn't crash).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from core.logging import get_logger
from services.execution.models import (
    ExecutionDomain,
    ExecutionLog,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    LogLevel,
    RollbackPlan,
)

_log = get_logger(__name__)

__all__ = [
    "DomainHandler",
    "FileSystemHandler",
    "TerminalHandler",
    "GitHandler",
    "DockerHandler",
    "SSHHandler",
    "DatabaseHandler",
    "RestApiHandler",
    "BrowserHandler",
    "DesktopHandler",
    "CloudHandler",
    "KubernetesHandler",
    "CICDHandler",
    "DocumentHandler",
    "SpreadsheetHandler",
    "EmailHandler",
    "CalendarHandler",
    "CommunicationHandler",
    "get_handler",
]


class DomainHandler(Protocol):
    """Protocol for domain handlers."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a request and return the result."""
        ...


def _make_result(
    request: ExecutionRequest,
    status: str = ExecutionStatus.SUCCEEDED.value,
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    output: Any = None,
    error: str | None = None,
    logs: list[ExecutionLog] | None = None,
    rollback_plan: RollbackPlan | None = None,
) -> ExecutionResult:
    """Helper to construct an ExecutionResult."""
    now = datetime.now(UTC)
    return ExecutionResult(
        execution_id=request.execution_id,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        output=output,
        error=error,
        started_at=now,
        completed_at=now,
        duration_s=0.0,
        logs=logs or [],
        rollback_plan=rollback_plan,
    )


# ============================================================
# Filesystem Handler
# ============================================================


class FileSystemHandler:
    """Handles filesystem operations: read, write, move, copy, delete, etc."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters

        try:
            if action == "read_file":
                return await self._read_file(request, params)
            elif action == "write_file":
                return await self._write_file(request, params)
            elif action == "move":
                return await self._move(request, params)
            elif action == "copy":
                return await self._copy(request, params)
            elif action == "delete_file":
                return await self._delete_file(request, params)
            elif action == "delete_directory":
                return await self._delete_directory(request, params)
            elif action == "list_directory":
                return await self._list_directory(request, params)
            elif action == "create_directory":
                return await self._create_directory(request, params)
            elif action == "checksum":
                return await self._checksum(request, params)
            else:
                return _make_result(request, status=ExecutionStatus.FAILED.value,
                                    exit_code=1, error=f"Unknown filesystem action: {action}")
        except Exception as e:
            return _make_result(request, status=ExecutionStatus.FAILED.value,
                                exit_code=1, error=str(e))
        finally:
            pass

    async def _read_file(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        path = Path(str(params.get("path", "")))
        if not path.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"File not found: {path}")
        content = path.read_text(encoding="utf-8", errors="replace")
        return _make_result(request, output=content, stdout=content[:5000])

    async def _write_file(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        path = Path(str(params.get("path", "")))
        content = str(params.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        rollback = RollbackPlan(
            steps=[{"action": "restore", "path": str(path), "existed": path.exists()}],
            rollback_reason="Restore original file",
        )
        if path.exists():
            rollback.steps[0]["original_content"] = path.read_text(encoding="utf-8", errors="replace")
        path.write_text(content, encoding="utf-8")
        return _make_result(request, stdout=f"Wrote {len(content)} bytes to {path}",
                            rollback_plan=rollback)

    async def _move(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        src = Path(str(params.get("source", "")))
        dst = Path(str(params.get("destination", "")))
        if not src.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return _make_result(request, stdout=f"Moved {src} → {dst}",
                            rollback_plan=RollbackPlan(steps=[{"action": "move_back", "src": str(dst), "dst": str(src)}]))

    async def _copy(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        src = Path(str(params.get("source", "")))
        dst = Path(str(params.get("destination", "")))
        if not src.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        return _make_result(request, stdout=f"Copied {src} → {dst}",
                            rollback_plan=RollbackPlan(steps=[{"action": "delete", "path": str(dst)}]))

    async def _delete_file(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        path = Path(str(params.get("path", "")))
        if not path.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"File not found: {path}")
        content = path.read_text(encoding="utf-8", errors="replace")
        path.unlink()
        return _make_result(request, stdout=f"Deleted {path}",
                            rollback_plan=RollbackPlan(steps=[{"action": "restore_file", "path": str(path), "content": content}]))

    async def _delete_directory(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        path = Path(str(params.get("path", "")))
        if not path.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"Directory not found: {path}")
        shutil.rmtree(str(path))
        return _make_result(request, stdout=f"Deleted directory {path}",
                            rollback_plan=RollbackPlan(steps=[{"action": "recreate_directory", "path": str(path)}]))

    async def _list_directory(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        path = Path(str(params.get("path", ".")))
        if not path.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"Directory not found: {path}")
        entries = [{"name": e.name, "type": "dir" if e.is_dir() else "file", "size": e.stat().st_size if e.is_file() else 0} for e in path.iterdir()]
        return _make_result(request, output=entries, stdout="\n".join(str(e["name"]) for e in entries))

    async def _create_directory(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        path = Path(str(params.get("path", "")))
        path.mkdir(parents=True, exist_ok=True)
        return _make_result(request, stdout=f"Created directory {path}",
                            rollback_plan=RollbackPlan(steps=[{"action": "delete_directory", "path": str(path)}]))

    async def _checksum(self, request: ExecutionRequest, params: dict[str, Any]) -> ExecutionResult:
        import hashlib
        path = Path(str(params.get("path", "")))
        if not path.exists():
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=f"File not found: {path}")
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return _make_result(request, output={"sha256": h.hexdigest()}, stdout=h.hexdigest())


# ============================================================
# Terminal Handler
# ============================================================


class TerminalHandler:
    """Handles terminal operations: run commands in bash/powershell/cmd."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters

        if action != "run_command":
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Unknown terminal action: {action}")

        command = str(params.get("command", ""))
        shell = str(params.get("shell", "bash"))
        cwd = params.get("cwd")
        env = params.get("env", {})
        timeout_s = float(params.get("timeout_s", request.timeout_s))

        if not command:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error="No command provided")

        start = time.perf_counter()
        try:
            # Build the command
            if shell in ("bash", "sh"):
                args = [shell, "-c", command]
            elif shell == "powershell":
                args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
            elif shell == "cmd":
                args = ["cmd", "/c", command]
            else:
                args = [shell, "-c", command]

            # Merge environment
            full_env = dict(os.environ)
            full_env.update(env)

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=full_env,
            )

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_s,
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = time.perf_counter() - start
                return ExecutionResult(
                    execution_id=request.execution_id,
                    status=ExecutionStatus.TIMEOUT.value,
                    exit_code=-1,
                    stderr=f"Command timed out after {timeout_s}s",
                    error="Timeout",
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    duration_s=elapsed,
                    logs=[ExecutionLog(level=LogLevel.ERROR.value, message=f"Timeout after {timeout_s}s", source="system")],
                )

            elapsed = time.perf_counter() - start
            exit_code = proc.returncode or 0
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            status = ExecutionStatus.SUCCEEDED.value if exit_code == 0 else ExecutionStatus.FAILED.value
            logs = [
                ExecutionLog(level=LogLevel.INFO.value, message=f"Command: {command}", source="system"),
            ]
            if stdout:
                logs.append(ExecutionLog(level=LogLevel.INFO.value, message=stdout[:2000], source="stdout"))
            if stderr:
                logs.append(ExecutionLog(level=LogLevel.WARNING.value if exit_code == 0 else LogLevel.ERROR.value, message=stderr[:2000], source="stderr"))

            return ExecutionResult(
                execution_id=request.execution_id,
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_s=elapsed,
                logs=logs,
            )
        except FileNotFoundError as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Shell not found: {e}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=str(e))


# ============================================================
# Git Handler
# ============================================================


class GitHandler:
    """Handles git operations: clone, pull, commit, push, branch, etc."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters

        try:
            if action == "clone":
                return await self._run_git(request, params, ["clone", params.get("url", ""), params.get("destination", ".")])
            elif action == "pull":
                return await self._run_git(request, params, ["pull"])
            elif action == "fetch":
                return await self._run_git(request, params, ["fetch"])
            elif action == "commit":
                return await self._run_git(request, params, ["commit", "-m", params.get("message", "")])
            elif action == "push":
                return await self._run_git(request, params, ["push"])
            elif action == "branch":
                return await self._run_git(request, params, ["branch"])
            elif action == "checkout":
                return await self._run_git(request, params, ["checkout", params.get("branch", "")])
            elif action == "merge":
                return await self._run_git(request, params, ["merge", params.get("branch", "")])
            elif action == "status":
                return await self._run_git(request, params, ["status"])
            elif action == "log":
                return await self._run_git(request, params, ["log", "--oneline", "-10"])
            elif action == "diff":
                return await self._run_git(request, params, ["diff"])
            else:
                return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                    error=f"Unknown git action: {action}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))

    async def _run_git(self, request: ExecutionRequest, params: dict[str, Any], git_args: list[str]) -> ExecutionResult:
        git_bin = shutil.which("git")
        if not git_bin:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error="git not found on PATH")
        cwd = params.get("cwd", ".")
        try:
            proc = await asyncio.create_subprocess_exec(
                git_bin, *git_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=request.timeout_s)
            exit_code = proc.returncode or 0
            status = ExecutionStatus.SUCCEEDED.value if exit_code == 0 else ExecutionStatus.FAILED.value
            return ExecutionResult(
                execution_id=request.execution_id,
                status=status,
                exit_code=exit_code,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_s=0.0,
                logs=[ExecutionLog(message=f"git {' '.join(git_args)}", source="system")],
            )
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Docker Handler (stub — requires docker binary)
# ============================================================


class DockerHandler:
    """Handles Docker operations: build, run, stop, logs, compose."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error="docker not found on PATH",
                                stderr="Docker binary is not installed. Install Docker to use this domain.")
        action = request.action
        params = request.parameters
        args_map: dict[str, list[str]] = {
            "ps": ["ps", "-a"],
            "images": ["images"],
            "build": ["build", "-t", params.get("tag", ""), params.get("path", ".")],
            "run": ["run", "-d"] + params.get("options", []) + [params.get("image", "")],
            "stop": ["stop", params.get("container", "")],
            "rm": ["rm", "-f", params.get("container", "")],
            "logs": ["logs", "--tail", "100", params.get("container", "")],
            "compose_up": ["compose", "up", "-d"],
            "compose_down": ["compose", "down"],
        }
        docker_args = args_map.get(action, [action])
        try:
            proc = await asyncio.create_subprocess_exec(
                docker_bin, *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=params.get("cwd"),
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=request.timeout_s)
            exit_code = proc.returncode or 0
            status = ExecutionStatus.SUCCEEDED.value if exit_code == 0 else ExecutionStatus.FAILED.value
            return ExecutionResult(
                execution_id=request.execution_id, status=status, exit_code=exit_code,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                started_at=datetime.now(UTC), completed_at=datetime.now(UTC), duration_s=0.0,
            )
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# SSH Handler (stub — requires ssh binary)
# ============================================================


class SSHHandler:
    """Handles SSH operations: remote commands, file transfer."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ssh_bin = shutil.which("ssh")
        if not ssh_bin:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error="ssh not found on PATH")
        params = request.parameters
        host = params.get("host", "")
        command = params.get("command", "")
        user = params.get("user", "")
        target = f"{user}@{host}" if user else host
        if not target:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error="No SSH host specified")
        try:
            ssh_args = [ssh_bin, "-o", "StrictHostKeyChecking=no", target, command]
            proc = await asyncio.create_subprocess_exec(
                *ssh_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=request.timeout_s)
            exit_code = proc.returncode or 0
            status = ExecutionStatus.SUCCEEDED.value if exit_code == 0 else ExecutionStatus.FAILED.value
            return ExecutionResult(
                execution_id=request.execution_id, status=status, exit_code=exit_code,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                started_at=datetime.now(UTC), completed_at=datetime.now(UTC), duration_s=0.0,
            )
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Database Handler (stub — uses sqlite3 for local, others need drivers)
# ============================================================


class DatabaseHandler:
    """Handles database operations: read, write, migrate, backup."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters
        db_type = params.get("type", "sqlite")
        if db_type != "sqlite":
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Database type '{db_type}' requires additional drivers. SQLite is supported natively.")
        import sqlite3
        db_path = params.get("path", ":memory:")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if action == "query":
                sql = params.get("sql", "")
                cursor.execute(sql)
                rows = [dict(r) for r in cursor.fetchall()]
                conn.close()
                return _make_result(request, output=rows, stdout=str(rows)[:5000])
            elif action == "execute":
                sql = params.get("sql", "")
                cursor.execute(sql)
                conn.commit()
                affected = cursor.rowcount
                conn.close()
                return _make_result(request, output={"rows_affected": affected}, stdout=f"{affected} rows affected")
            elif action == "tables":
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall()]
                conn.close()
                return _make_result(request, output=tables, stdout=str(tables))
            else:
                conn.close()
                return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                    error=f"Unknown database action: {action}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# REST API Handler
# ============================================================


class RestApiHandler:
    """Handles REST API operations: GET, POST, PUT, PATCH, DELETE."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters
        url = params.get("url", "")
        method = action.upper() if action in ("get", "post", "put", "patch", "delete") else "GET"
        headers = params.get("headers", {})
        body = params.get("body")
        timeout_s = float(params.get("timeout_s", request.timeout_s))
        if not url:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error="No URL provided")
        try:
            import json as _json
            import urllib.error
            import urllib.request
            data = None
            if body:
                data = _json.dumps(body).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    status_code = resp.status
                    resp_body = resp.read().decode("utf-8", errors="replace")
                    try:
                        resp_json = _json.loads(resp_body)
                    except (ValueError, TypeError):
                        resp_json = None
                    return ExecutionResult(
                        execution_id=request.execution_id,
                        status=ExecutionStatus.SUCCEEDED.value if 200 <= status_code < 300 else ExecutionStatus.FAILED.value,
                        exit_code=status_code,
                        stdout=resp_body[:5000],
                        output={"status_code": status_code, "body": resp_json or resp_body[:2000]},
                        started_at=datetime.now(UTC), completed_at=datetime.now(UTC), duration_s=0.0,
                    )
            except urllib.error.HTTPError as e:
                resp_body = e.read().decode("utf-8", errors="replace")
                return ExecutionResult(
                    execution_id=request.execution_id,
                    status=ExecutionStatus.FAILED.value,
                    exit_code=e.code,
                    stderr=resp_body[:2000],
                    error=f"HTTP {e.code}: {e.reason}",
                    started_at=datetime.now(UTC), completed_at=datetime.now(UTC), duration_s=0.0,
                )
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Browser Handler (stub — requires playwright)
# ============================================================


class BrowserHandler:
    """Handles browser automation via Playwright.

    Gracefully degrades when Playwright is not installed — returns a clear
    error with installation instructions instead of crashing.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return _make_result(
                request, ExecutionStatus.FAILED.value, 1,
                error="Playwright is not installed. Install with: pip install playwright && playwright install chromium",
                stderr="Optional dependency 'playwright' not available. Browser automation requires Playwright.",
            )
        action = request.action
        params = request.parameters
        browser_type = params.get("browser", "chromium")
        try:
            async with async_playwright() as p:
                browser = await getattr(p, browser_type).launch()
                page = await browser.new_page()
                if action == "navigate":
                    url = params.get("url", "")
                    await page.goto(url)
                    title = await page.title()
                    await browser.close()
                    return _make_result(request, output={"url": url, "title": title},
                                        stdout=f"Navigated to {url} — title: {title}")
                elif action == "screenshot":
                    url = params.get("url", "")
                    await page.goto(url)
                    screenshot_bytes = await page.screenshot()
                    await browser.close()
                    return _make_result(request, output={"screenshot_size": len(screenshot_bytes)},
                                        stdout=f"Screenshot taken ({len(screenshot_bytes)} bytes)")
                elif action == "extract_text":
                    url = params.get("url", "")
                    await page.goto(url)
                    text = await page.inner_text("body")
                    await browser.close()
                    return _make_result(request, output={"text": text[:5000]},
                                        stdout=text[:2000])
                elif action == "click":
                    url = params.get("url", "")
                    selector = params.get("selector", "")
                    await page.goto(url)
                    await page.click(selector)
                    await browser.close()
                    return _make_result(request, stdout=f"Clicked '{selector}' on {url}")
                elif action == "fill":
                    url = params.get("url", "")
                    selector = params.get("selector", "")
                    value = params.get("value", "")
                    await page.goto(url)
                    await page.fill(selector, value)
                    await browser.close()
                    return _make_result(request, stdout=f"Filled '{selector}' with '{value}' on {url}")
                else:
                    await browser.close()
                    return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                        error=f"Unknown browser action: {action}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Desktop Handler — graceful degradation
# ============================================================


class DesktopHandler:
    """Handles desktop automation via pyautogui (cross-platform).

    Gracefully degrades when pyautogui is not installed.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            import pyautogui  # noqa: F401
        except ImportError:
            return _make_result(
                request, ExecutionStatus.FAILED.value, 1,
                error="Desktop automation requires pyautogui. Install with: pip install pyautogui",
                stderr="Optional dependency 'pyautogui' not available. Desktop automation requires pyautogui.",
            )
        action = request.action
        params = request.parameters
        try:
            import pyautogui
            if action == "screenshot":
                screenshot = pyautogui.screenshot()
                import io
                buf = io.BytesIO()
                screenshot.save(buf, format="PNG")
                return _make_result(request, output={"screenshot_size": len(buf.getvalue())},
                                    stdout=f"Screenshot taken ({len(buf.getvalue())} bytes)")
            elif action == "click":
                x = int(params.get("x", 0))
                y = int(params.get("y", 0))
                pyautogui.click(x, y)
                return _make_result(request, stdout=f"Clicked at ({x}, {y})")
            elif action == "type_text":
                text = params.get("text", "")
                pyautogui.typewrite(text)
                return _make_result(request, stdout=f"Typed '{text[:50]}'")
            elif action == "press_key":
                key = params.get("key", "")
                pyautogui.press(key)
                return _make_result(request, stdout=f"Pressed '{key}'")
            else:
                return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                    error=f"Unknown desktop action: {action}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Cloud Handler — graceful degradation via cloud SDKs
# ============================================================


class CloudHandler:
    """Handles cloud operations: AWS (boto3), Azure, GCP.

    Gracefully degrades when cloud SDKs are not installed.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        provider = request.parameters.get("provider", "aws")
        if provider == "aws":
            return await self._execute_aws(request)
        elif provider == "azure":
            return await self._execute_azure(request)
        elif provider == "gcp":
            return await self._execute_gcp(request)
        else:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Unsupported cloud provider: {provider}")

    async def _execute_aws(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            import boto3  # noqa: F401
        except ImportError:
            return _make_result(
                request, ExecutionStatus.FAILED.value, 1,
                error="AWS operations require boto3. Install with: pip install boto3",
                stderr="Optional dependency 'boto3' not available. Configure AWS credentials to enable.",
            )
        action = request.action
        params = request.parameters
        try:
            import boto3
            if action == "list_instances":
                ec2 = boto3.client("ec2", region_name=params.get("region", "us-east-1"))
                resp = ec2.describe_instances()
                instances = []
                for res in resp.get("Reservations", []):
                    for inst in res.get("Instances", []):
                        instances.append({
                            "id": inst.get("InstanceId", ""),
                            "state": inst.get("State", {}).get("Name", ""),
                            "type": inst.get("InstanceType", ""),
                        })
                return _make_result(request, output=instances, stdout=f"{len(instances)} instances")
            elif action == "list_buckets":
                s3 = boto3.client("s3")
                resp = s3.list_buckets()
                buckets = [b["Name"] for b in resp.get("Buckets", [])]
                return _make_result(request, output=buckets, stdout=f"{len(buckets)} buckets")
            else:
                return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                    error=f"Unknown AWS action: {action}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))

    async def _execute_azure(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            from azure.identity import (
                DefaultAzureCredential,  # noqa: F401
            )
        except ImportError:
            return _make_result(
                request, ExecutionStatus.FAILED.value, 1,
                error="Azure operations require azure-identity. Install with: pip install azure-identity",
                stderr="Optional dependency 'azure-identity' not available.",
            )
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Azure operations configured but action not implemented")

    async def _execute_gcp(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            from google.cloud import storage  # noqa: F401
        except ImportError:
            return _make_result(
                request, ExecutionStatus.FAILED.value, 1,
                error="GCP operations require google-cloud-storage. Install with: pip install google-cloud-storage",
                stderr="Optional dependency 'google-cloud-storage' not available.",
            )
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="GCP operations configured but action not implemented")


# ============================================================
# Kubernetes Handler (stub — requires kubectl)
# ============================================================


class KubernetesHandler:
    """Handles Kubernetes operations: deployments, pods, services, etc."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        kubectl = shutil.which("kubectl")
        if not kubectl:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error="kubectl not found on PATH")
        action = request.action
        params = request.parameters
        resource = params.get("resource", "pods")
        name = params.get("name", "")
        namespace = params.get("namespace", "default")
        k8s_args = ["kubectl", "-n", namespace]
        if action == "get":
            k8s_args += ["get", resource]
        elif action == "describe":
            k8s_args += ["describe", resource, name]
        elif action == "logs":
            k8s_args += ["logs", name]
        elif action == "delete":
            k8s_args += ["delete", resource, name]
        elif action == "scale":
            k8s_args += ["scale", resource, name, f"--replicas={params.get('replicas', 1)}"]
        else:
            k8s_args += [action, resource]
        try:
            proc = await asyncio.create_subprocess_exec(
                *k8s_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=request.timeout_s)
            exit_code = proc.returncode or 0
            status = ExecutionStatus.SUCCEEDED.value if exit_code == 0 else ExecutionStatus.FAILED.value
            return ExecutionResult(
                execution_id=request.execution_id, status=status, exit_code=exit_code,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                started_at=datetime.now(UTC), completed_at=datetime.now(UTC), duration_s=0.0,
            )
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# CI/CD Handler (stub — requires API tokens)
# ============================================================


class CICDHandler:
    """Handles CI/CD operations: GitHub Actions, GitLab CI, Jenkins.

    Uses REST API calls (urllib) — no SDK required. Requires API tokens
    configured in parameters.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        params = request.parameters
        platform = params.get("platform", "github")
        token = params.get("token", "")
        if not token:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"CI/CD operations require an API token for {platform}. "
                                      "Provide via parameters.token.")
        try:
            import json as _json
            import urllib.error
            import urllib.request
            if platform == "github":
                repo = params.get("repo", "")
                api_url = f"https://api.github.com/repos/{repo}/actions/runs"
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(req, timeout=request.timeout_s) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    runs = data.get("workflow_runs", [])
                    return _make_result(request, output={"runs": len(runs), "latest": runs[0]["status"] if runs else "none"},
                                        stdout=f"{len(runs)} workflow runs found")
            elif platform == "gitlab":
                project_id = params.get("project_id", "")
                gitlab_url = params.get("url", "https://gitlab.com")
                api_url = f"{gitlab_url}/api/v4/projects/{project_id}/pipelines"
                headers = {"PRIVATE-TOKEN": token}
                req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(req, timeout=request.timeout_s) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    return _make_result(request, output={"pipelines": len(data)},
                                        stdout=f"{len(data)} pipelines found")
            else:
                return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                    error=f"Unsupported CI/CD platform: {platform}")
        except urllib.error.HTTPError as e:
            return _make_result(request, ExecutionStatus.FAILED.value, e.code,
                                error=f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Document Handler — graceful degradation
# ============================================================


class DocumentHandler:
    """Handles document automation: create/edit Word, Markdown, PDF, text.

    For .docx: requires python-docx (graceful degradation if missing).
    For .md/.txt/.pdf: uses standard library / reportlab.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters
        if action == "create_markdown":
            path = params.get("path", "")
            content = params.get("content", "")
            Path(path).write_text(content, encoding="utf-8")
            return _make_result(request, stdout=f"Created markdown: {path} ({len(content)} chars)")
        elif action == "create_text":
            path = params.get("path", "")
            content = params.get("content", "")
            Path(path).write_text(content, encoding="utf-8")
            return _make_result(request, stdout=f"Created text file: {path} ({len(content)} chars)")
        elif action == "create_docx":
            try:
                from docx import Document
            except ImportError:
                return _make_result(
                    request, ExecutionStatus.FAILED.value, 1,
                    error="DOCX creation requires python-docx. Install with: pip install python-docx",
                    stderr="Optional dependency 'python-docx' not available.",
                )
            path = params.get("path", "")
            content = params.get("content", "")
            doc = Document()
            for line in content.split("\n"):
                doc.add_paragraph(line)
            doc.save(path)
            return _make_result(request, stdout=f"Created DOCX: {path}")
        elif action == "create_pdf":
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
            except ImportError:
                return _make_result(
                    request, ExecutionStatus.FAILED.value, 1,
                    error="PDF creation requires reportlab. Install with: pip install reportlab",
                    stderr="Optional dependency 'reportlab' not available.",
                )
            path = params.get("path", "")
            content = params.get("content", "")
            c = canvas.Canvas(path, pagesize=letter)
            y = 750
            for line in content.split("\n"):
                c.drawString(72, y, line[:90])
                y -= 12
                if y < 50:
                    c.showPage()
                    y = 750
            c.save()
            return _make_result(request, stdout=f"Created PDF: {path}")
        else:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Unknown document action: {action}")


# ============================================================
# Spreadsheet Handler — graceful degradation
# ============================================================


class SpreadsheetHandler:
    """Handles spreadsheet automation: CSV (native), Excel (openpyxl).

    CSV operations work with the standard library. Excel requires openpyxl.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters
        if action == "create_csv":
            import csv
            import io
            path = params.get("path", "")
            rows = params.get("rows", [])
            output = io.StringIO()
            writer = csv.writer(output)
            for row in rows:
                writer.writerow(row)
            Path(path).write_text(output.getvalue(), encoding="utf-8")
            return _make_result(request, stdout=f"Created CSV: {path} ({len(rows)} rows)")
        elif action == "read_csv":
            import csv
            path = params.get("path", "")
            with Path(path).open(encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [list(r) for r in reader]
            return _make_result(request, output=rows, stdout=f"{len(rows)} rows read")
        elif action == "create_excel":
            try:
                from openpyxl import Workbook
            except ImportError:
                return _make_result(
                    request, ExecutionStatus.FAILED.value, 1,
                    error="Excel creation requires openpyxl. Install with: pip install openpyxl",
                    stderr="Optional dependency 'openpyxl' not available.",
                )
            path = params.get("path", "")
            rows = params.get("rows", [])
            wb = Workbook()
            ws = wb.active
            for row in rows:
                ws.append(row)
            wb.save(path)
            return _make_result(request, stdout=f"Created Excel: {path} ({len(rows)} rows)")
        else:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Unknown spreadsheet action: {action}")


# ============================================================
# Email Handler — graceful degradation
# ============================================================


class EmailHandler:
    """Handles email automation via SMTP/IMAP.

    Uses smtplib (standard library). Requires SMTP credentials in parameters.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters
        if action != "send":
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Unknown email action: {action}")
        smtp_host = params.get("smtp_host", "")
        smtp_port = int(params.get("smtp_port", 587))
        username = params.get("username", "")
        password = params.get("password", "")
        from_addr = params.get("from", username)
        to_addrs = params.get("to", [])
        subject = params.get("subject", "")
        body = params.get("body", "")
        if not smtp_host or not to_addrs:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error="Email requires smtp_host, to, and (username/password or smtp config)")
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_port != 25:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(from_addr, to_addrs, msg.as_string())
            return _make_result(request, stdout=f"Email sent to {len(to_addrs)} recipient(s)")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Calendar Handler — graceful degradation
# ============================================================


class CalendarHandler:
    """Handles calendar automation: create ICS files, schedule events.

    ICS generation works with the standard library. Google Calendar /
    Microsoft Graph require additional SDKs and credentials.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        action = request.action
        params = request.parameters
        if action == "create_ics":
            title = params.get("title", "")
            start = params.get("start", "")
            end = params.get("end", "")
            description = params.get("description", "")
            location = params.get("location", "")
            ics_content = self._generate_ics(title, start, end, description, location)
            path = params.get("path", "")
            if path:
                Path(path).write_text(ics_content, encoding="utf-8")
                return _make_result(request, stdout=f"ICS file created: {path}")
            return _make_result(request, output={"ics": ics_content},
                                stdout=f"ICS generated ({len(ics_content)} bytes)")
        else:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error=f"Unknown calendar action: {action}. Supported: create_ics")

    def _generate_ics(self, title: str, start: str, end: str, description: str, location: str) -> str:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AAiOS//Calendar//EN",
            "BEGIN:VEVENT",
            f"UID:{uuid4().hex}@aaios",
            f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{location}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return "\r\n".join(lines) + "\r\n"


# ============================================================
# Communication Handler — graceful degradation
# ============================================================


class CommunicationHandler:
    """Handles communication automation: Slack, Discord, webhooks.

    Uses urllib (standard library) — no SDK required. Requires webhook URLs
    or API tokens configured in parameters.
    """

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        params = request.parameters
        platform = params.get("platform", "webhook")
        message = params.get("message", "")
        if not message:
            return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                error="Communication requires a 'message' parameter")
        try:
            import json as _json
            import urllib.request
            if platform == "webhook":
                webhook_url = params.get("url", "")
                if not webhook_url:
                    return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                        error="Webhook requires 'url' parameter")
                data = _json.dumps({"text": message, "content": message}).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url, data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=request.timeout_s) as resp:
                    status_code = resp.status
                return _make_result(request, exit_code=status_code,
                                    stdout=f"Message sent via webhook (HTTP {status_code})")
            elif platform == "slack":
                token = params.get("token", "")
                channel = params.get("channel", "#general")
                if not token:
                    return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                        error="Slack requires 'token' parameter")
                data = _json.dumps({"channel": channel, "text": message}).encode("utf-8")
                req = urllib.request.Request(
                    "https://slack.com/api/chat.postMessage",
                    data=data,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=request.timeout_s) as resp:
                    resp_data = _json.loads(resp.read().decode("utf-8"))
                if resp_data.get("ok"):
                    return _make_result(request, stdout=f"Slack message sent to {channel}")
                else:
                    return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                        error=f"Slack error: {resp_data.get('error', 'unknown')}")
            elif platform == "discord":
                webhook_url = params.get("url", "")
                if not webhook_url:
                    return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                        error="Discord requires webhook 'url' parameter")
                data = _json.dumps({"content": message}).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url, data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=request.timeout_s) as resp:
                    status_code = resp.status
                return _make_result(request, exit_code=status_code,
                                    stdout=f"Discord message sent (HTTP {status_code})")
            else:
                return _make_result(request, ExecutionStatus.FAILED.value, 1,
                                    error=f"Unsupported platform: {platform}. Use webhook, slack, or discord.")
        except Exception as e:
            return _make_result(request, ExecutionStatus.FAILED.value, 1, error=str(e))


# ============================================================
# Handler registry
# ============================================================


_HANDLERS: dict[str, DomainHandler] = {
    ExecutionDomain.FILESYSTEM.value: FileSystemHandler(),
    ExecutionDomain.TERMINAL.value: TerminalHandler(),
    ExecutionDomain.GIT.value: GitHandler(),
    ExecutionDomain.DOCKER.value: DockerHandler(),
    ExecutionDomain.SSH.value: SSHHandler(),
    ExecutionDomain.DATABASE.value: DatabaseHandler(),
    ExecutionDomain.REST_API.value: RestApiHandler(),
    ExecutionDomain.BROWSER.value: BrowserHandler(),
    ExecutionDomain.DESKTOP.value: DesktopHandler(),
    ExecutionDomain.CLOUD.value: CloudHandler(),
    ExecutionDomain.KUBERNETES.value: KubernetesHandler(),
    ExecutionDomain.CI_CD.value: CICDHandler(),
    ExecutionDomain.DOCUMENT.value: DocumentHandler(),
    ExecutionDomain.SPREADSHEET.value: SpreadsheetHandler(),
    ExecutionDomain.EMAIL.value: EmailHandler(),
    ExecutionDomain.CALENDAR.value: CalendarHandler(),
    ExecutionDomain.COMMUNICATION.value: CommunicationHandler(),
}


def get_handler(domain: str) -> DomainHandler | None:
    """Get the handler for a domain, or None if not found."""
    return _HANDLERS.get(domain)
