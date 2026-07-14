"""Tests for core.platform — platform adapters (Windows primary, Linux stub)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.platform import LinuxPlatform, WindowsPlatform, get_platform, get_platform_name


@pytest.mark.offline
class TestPlatformDetection:
    """Platform detection tests."""

    def test_get_platform_name_matches_sys_platform(self) -> None:
        name = get_platform_name()
        if sys.platform == "win32":
            assert name == "windows"
        else:
            assert name == "linux"

    def test_get_platform_returns_correct_adapter(self) -> None:
        platform = get_platform()
        if sys.platform == "win32":
            assert platform.is_windows is True
            assert platform.is_linux is False
        else:
            assert platform.is_windows is False
            assert platform.is_linux is True


@pytest.mark.offline
class TestWindowsPlatform:
    """WindowsPlatform tests (run on any OS — testing the class directly)."""

    def test_name(self) -> None:
        assert WindowsPlatform().name == "windows"

    def test_is_windows(self) -> None:
        assert WindowsPlatform().is_windows is True

    def test_is_linux(self) -> None:
        assert WindowsPlatform().is_linux is False

    def test_supported(self) -> None:
        assert WindowsPlatform().supported() is True

    def test_config_dir_path(self) -> None:
        p = WindowsPlatform()
        # Should contain 'AAiOS' and 'config'
        assert "AAiOS" in str(p.config_dir)
        assert "config" in str(p.config_dir)

    def test_normalize_path_forward_slash_to_backslash(self) -> None:
        p = WindowsPlatform()
        norm = p.normalize_path("C:/Users/alice/file.txt")
        # Should have backslashes (Windows form)
        assert "\\" in str(norm)

    def test_default_shell_returns_nonempty(self) -> None:
        p = WindowsPlatform()
        # On Linux test env, this might be 'cmd.exe' as fallback — that's fine
        assert p.default_shell() != ""

    def test_is_path_safe_within_sandbox(self) -> None:
        p = WindowsPlatform()
        sandbox = Path("C:\\Users\\alice\\project")
        inside = Path("C:\\Users\\alice\\project\\file.txt")
        assert p.is_path_safe(inside, sandbox) is True

    def test_is_path_safe_outside_sandbox(self) -> None:
        p = WindowsPlatform()
        sandbox = Path("C:\\Users\\alice\\project")
        outside = Path("C:\\Users\\bob\\file.txt")
        assert p.is_path_safe(outside, sandbox) is False


@pytest.mark.offline
class TestLinuxPlatform:
    """LinuxPlatform tests — Linux is stubbed in v1."""

    def test_name(self) -> None:
        assert LinuxPlatform().name == "linux"

    def test_is_windows(self) -> None:
        assert LinuxPlatform().is_windows is False

    def test_is_linux(self) -> None:
        assert LinuxPlatform().is_linux is True

    def test_not_supported_in_v1(self) -> None:
        assert LinuxPlatform().supported() is False

    def test_config_dir_path(self) -> None:
        p = LinuxPlatform()
        assert str(p.config_dir) == "/etc/aaios"

    def test_data_dir_path(self) -> None:
        p = LinuxPlatform()
        assert str(p.data_dir) == "/var/lib/aaios"

    def test_log_dir_path(self) -> None:
        p = LinuxPlatform()
        assert str(p.log_dir) == "/var/log/aaios"

    def test_temp_dir_path(self) -> None:
        p = LinuxPlatform()
        assert str(p.temp_dir) == "/tmp/aaios"

    def test_default_shell_is_bash(self) -> None:
        p = LinuxPlatform()
        # Either SHELL env var or /bin/bash
        shell = p.default_shell()
        assert "bash" in shell or "sh" in shell

    def test_exec_shell_raises_not_implemented(self) -> None:
        p = LinuxPlatform()
        with pytest.raises(NotImplementedError, match="v1.1"):
            import asyncio

            asyncio.run(p.exec_shell("echo hi"))

    def test_is_path_safe_within_sandbox(self) -> None:
        p = LinuxPlatform()
        sandbox = Path("/tmp/sandbox")
        inside = Path("/tmp/sandbox/file.txt")
        assert p.is_path_safe(inside, sandbox) is True

    def test_is_path_safe_outside_sandbox(self) -> None:
        p = LinuxPlatform()
        sandbox = Path("/tmp/sandbox")
        outside = Path("/etc/passwd")
        assert p.is_path_safe(outside, sandbox) is False
