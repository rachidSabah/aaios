"""Tests for core.logging — structlog setup, context binding."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from core.logging import (
    LoggingConfig,
    bind_context,
    clear_context,
    get_logger,
    init_logging,
    shutdown_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset logging state before each test."""
    init_logging(LoggingConfig(level="INFO", json_output=True))
    yield
    clear_context()
    shutdown_logging()


def _read_log_output(capsys: pytest.CaptureFixture[str]) -> str:
    """Read combined stdout + captured log records."""
    captured = capsys.readouterr()
    # structlog → stdlib logging → pytest captures log records separately
    # The handler is on stdout, so the JSON line should be in captured.out
    return captured.out


@pytest.mark.offline
class TestLogging:
    """Logging system tests."""

    def test_logger_returns_bound_logger(self) -> None:
        log = get_logger("test")
        assert log is not None

    def test_json_output_format(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        log = get_logger("test")
        log.info("test.event", key="value")
        # structlog output goes through stdlib logging; check both capture paths
        all_output = capsys.readouterr().out + "\n".join(r.getMessage() for r in caplog.records)
        # The structlog JSON output should contain these keys somewhere
        combined = all_output
        assert "test.event" in combined
        assert "value" in combined

    def test_correlation_id_in_output(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with bind_context(correlation_id="task-123"):
            log = get_logger("test")
            log.info("task.event")
        combined = capsys.readouterr().out + "\n".join(r.getMessage() for r in caplog.records)
        assert "task-123" in combined

    def test_actor_in_output(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with bind_context(actor="agent:claude-code"):
            log = get_logger("test")
            log.info("agent.event")
        combined = capsys.readouterr().out + "\n".join(r.getMessage() for r in caplog.records)
        assert "agent:claude-code" in combined

    def test_context_is_cleared_after_block(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with bind_context(correlation_id="task-1"):
            pass
        log = get_logger("test")
        log.info("after_block")
        combined = capsys.readouterr().out + "\n".join(r.getMessage() for r in caplog.records)
        # Should NOT have the correlation_id from the previous block
        assert "task-1" not in combined

    def test_extra_context_fields(
        self,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with bind_context(custom_field="custom_value"):
            log = get_logger("test")
            log.info("test.event")
        combined = capsys.readouterr().out + "\n".join(r.getMessage() for r in caplog.records)
        assert "custom_value" in combined

    def test_text_format_when_json_disabled(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        shutdown_logging()
        init_logging(LoggingConfig(level="INFO", json_output=False))
        log = get_logger("test")
        log.info("plain.event")
        captured = capsys.readouterr()
        assert "plain.event" in captured.out

    def test_file_logging(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        shutdown_logging()
        init_logging(LoggingConfig(level="INFO", json_output=True, log_file=log_file))
        log = get_logger("test")
        log.info("file.event")
        # Need to flush — structlog uses stdlib logging under the hood
        logging.shutdown()
        assert log_file.is_file()
        content = log_file.read_text(encoding="utf-8")
        assert "file.event" in content

    def test_log_level_filtering(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        shutdown_logging()
        init_logging(LoggingConfig(level="WARNING", json_output=True))
        log = get_logger("test")
        log.info("should.be.filtered")
        log.warning("should.appear")
        captured = capsys.readouterr()
        assert "should.be.filtered" not in captured.out
        assert "should.appear" in captured.out
