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
    """Handles browser automation: navigate, click, input, screenshot."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Browser automation requires playwright. Install with: pip install playwright && playwright install",
                            stderr="Playwright not available. This is a stub handler.")


# ============================================================
# Desktop Handler (stub — requires platform-specific tools)
# ============================================================


class DesktopHandler:
    """Handles desktop automation: mouse, keyboard, screenshots, OCR."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Desktop automation requires platform-specific tools (pyautogui, etc.)",
                            stderr="Desktop tools not available. This is a stub handler.")


# ============================================================
# Cloud Handler (stub — requires cloud SDKs)
# ============================================================


class CloudHandler:
    """Handles cloud operations: AWS, Azure, GCP, etc."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Cloud operations require cloud SDKs (boto3, azure-sdk, google-cloud). Configure credentials to enable.",
                            stderr="Cloud SDK not configured. This is a stub handler.")


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
    """Handles CI/CD operations: GitHub Actions, GitLab CI, Jenkins."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="CI/CD operations require API tokens. Configure GitHub/GitLab/Jenkins credentials to enable.",
                            stderr="CI/CD credentials not configured. This is a stub handler.")


# ============================================================
# Document Handler (stub — requires python-docx, python-pptx)
# ============================================================


class DocumentHandler:
    """Handles document automation: create/edit Word, PowerPoint, PDF."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Document automation requires python-docx, python-pptx. Install to enable.",
                            stderr="Document libraries not available. This is a stub handler.")


# ============================================================
# Spreadsheet Handler (stub — requires openpyxl)
# ============================================================


class SpreadsheetHandler:
    """Handles spreadsheet automation: create/edit Excel, CSV."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Spreadsheet automation requires openpyxl. Install to enable.",
                            stderr="Spreadsheet libraries not available. This is a stub handler.")


# ============================================================
# Email Handler (stub — requires SMTP credentials)
# ============================================================


class EmailHandler:
    """Handles email automation: send, read, search."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Email automation requires SMTP/IMAP credentials. Configure to enable.",
                            stderr="Email credentials not configured. This is a stub handler.")


# ============================================================
# Calendar Handler (stub — requires calendar API)
# ============================================================


class CalendarHandler:
    """Handles calendar automation: create events, check availability."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Calendar automation requires Google/Microsoft calendar API credentials. Configure to enable.",
                            stderr="Calendar API not configured. This is a stub handler.")


# ============================================================
# Communication Handler (stub — requires Slack/Teams API)
# ============================================================


class CommunicationHandler:
    """Handles communication automation: Slack, Teams, Discord."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _make_result(request, ExecutionStatus.FAILED.value, 1,
                            error="Communication automation requires Slack/Teams/Discord API tokens. Configure to enable.",
                            stderr="Communication API not configured. This is a stub handler.")


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
