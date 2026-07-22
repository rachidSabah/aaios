"""Diagnostics Manager and Crash Reporter — system health and error tracking.

The DiagnosticsManager collects system health data, runs checks, and provides
a unified view for the Mission Control Dashboard. The CrashReporter captures
unhandled exceptions, persists crash dumps, and publishes crash events on the
Event Bus so the update/rollback system can react.
"""

from __future__ import annotations

import json
import platform
import sys
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.event_bus import get_bus
from core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class DiagnosticCheck:
    """Result of a single diagnostic check."""

    name: str
    status: str  # pass, fail, warn, error
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrashReport:
    """A captured crash/exception report."""

    id: str
    timestamp: str
    exception_type: str
    exception_message: str
    traceback: str
    version: str
    platform: str
    component: str = "unknown"
    resolved: bool = False


class DiagnosticsManager:
    """Run health checks and collect system diagnostics."""

    def __init__(self) -> None:
        self._checks: dict[str, DiagnosticCheck] = {}

    async def run_all(self) -> list[DiagnosticCheck]:
        """Run all diagnostic checks."""
        checks = [
            self._check_python_version,
            self._check_disk_space,
            self._check_event_bus,
            self._check_platform,
        ]
        results: list[DiagnosticCheck] = []
        for check_fn in checks:
            try:
                result = await check_fn()
            except Exception as exc:  # noqa: BLE001
                result = DiagnosticCheck(
                    name=check_fn.__name__,
                    status="error",
                    message=str(exc),
                )
            self._checks[result.name] = result
            results.append(result)
        return results

    def get_check(self, name: str) -> DiagnosticCheck | None:
        return self._checks.get(name)

    def all_checks(self) -> list[DiagnosticCheck]:
        return list(self._checks.values())

    async def _check_python_version(self) -> DiagnosticCheck:
        v = sys.version_info
        ok = v.major >= 3 and v.minor >= 12
        return DiagnosticCheck(
            name="python_version",
            status="pass" if ok else "fail",
            message=f"Python {v.major}.{v.minor}.{v.micro}",
            details={"version": f"{v.major}.{v.minor}.{v.micro}", "required": ">=3.12"},
        )

    async def _check_disk_space(self) -> DiagnosticCheck:
        try:
            import shutil

            usage = shutil.disk_usage(Path.cwd())
            free_gb = usage.free / (1024**3)
            ok = free_gb > 1.0
            return DiagnosticCheck(
                name="disk_space",
                status="pass" if ok else "warn",
                message=f"{free_gb:.1f} GB free",
                details={
                    "free_gb": round(free_gb, 1),
                    "total_gb": round(usage.total / (1024**3), 1),
                },
            )
        except Exception as exc:
            return DiagnosticCheck(name="disk_space", status="warn", message=str(exc))

    async def _check_event_bus(self) -> DiagnosticCheck:
        try:
            bus = get_bus()
            subs = bus.subscriber_count()
            return DiagnosticCheck(
                name="event_bus",
                status="pass",
                message=f"{subs} subscribers",
                details={"subscribers": subs, "topics": bus.topics()},
            )
        except RuntimeError as exc:
            return DiagnosticCheck(name="event_bus", status="warn", message=str(exc))

    async def _check_platform(self) -> DiagnosticCheck:
        try:
            from core.platform import get_platform

            plat = get_platform()
            return DiagnosticCheck(
                name="platform",
                status="pass" if plat.supported() else "warn",
                message=f"{plat.name} ({'supported' if plat.supported() else 'stub'})",
                details={"platform": plat.name, "supported": plat.supported()},
            )
        except Exception as exc:
            return DiagnosticCheck(name="platform", status="error", message=str(exc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "checks": {
                name: {"status": c.status, "message": c.message, "details": c.details}
                for name, c in self._checks.items()
            },
            "system": {
                "platform": platform.platform(),
                "python": sys.version,
                "host": platform.node(),
            },
        }

    async def shutdown(self) -> None:
        self._checks.clear()
        _log.info("desktop.diagnostics.shutdown")


class CrashReporter:
    """Capture unhandled exceptions and persist crash reports."""

    def __init__(self, crash_dir: str | Path | None = None) -> None:
        self._crash_dir = Path(crash_dir or "desktop_data/crashes")
        self._crash_dir.mkdir(parents=True, exist_ok=True)
        self._reports: dict[str, CrashReport] = {}

    def capture(self, exc: BaseException, *, component: str = "unknown") -> CrashReport:
        """Capture an exception and persist the crash report."""
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        report = CrashReport(
            id=str(uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback=tb,
            version="1.0.0-rc1",
            platform=sys.platform,
            component=component,
        )
        self._reports[report.id] = report
        self._persist(report)
        _log.error("desktop.crash.captured", report_id=report.id, component=component, exc_info=exc)
        return report

    def list_reports(self) -> list[CrashReport]:
        return list(self._reports.values())

    def get_report(self, report_id: str) -> CrashReport | None:
        return self._reports.get(report_id)

    def resolve(self, report_id: str) -> bool:
        report = self._reports.get(report_id)
        if report is None:
            return False
        report.resolved = True
        return True

    def _persist(self, report: CrashReport) -> None:
        try:
            path = self._crash_dir / f"crash_{report.id}.json"
            path.write_text(
                json.dumps(
                    {
                        "id": report.id,
                        "timestamp": report.timestamp,
                        "exception_type": report.exception_type,
                        "exception_message": report.exception_message,
                        "traceback": report.traceback,
                        "version": report.version,
                        "platform": report.platform,
                        "component": report.component,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("desktop.crash.persist_failed", error=str(exc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "crash_dir": str(self._crash_dir),
            "total_reports": len(self._reports),
        }

    async def shutdown(self) -> None:
        pass
