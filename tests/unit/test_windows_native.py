"""Tests for the Windows Native Service."""

from __future__ import annotations

import sys

import pytest

from services.windows_native import (
    AppContainerManager,
    FilePathRule,
    JobObjectManager,
    JobResourceLimits,
    JobState,
    PolicyState,
    PublisherRule,
    SandboxCapability,
    ScheduledTaskNotFoundError,
    ServiceConfig,
    ServiceState,
    SignerRule,
    TaskAction,
    TaskSchedulerManager,
    TaskTrigger,
    TriggerType,
    WDACManager,
    WindowsServicesManager,
)


@pytest.mark.offline
class TestWindowsServices:
    """WindowsServicesManager tests."""

    async def test_create_service_on_non_windows(self) -> None:
        mgr = WindowsServicesManager()
        config = ServiceConfig(
            bin_path=r"C:\AAiOS\agent.exe",
            display_name="AAiOS Agent",
            description="Test agent service",
            start_type="auto",
        )
        # On non-Windows, this returns a stub status
        status = await mgr.create("AAiOSAgent", config)
        assert status.name == "AAiOSAgent"
        assert status.display_name == "AAiOS Agent"
        if sys.platform != "win32":
            assert status.state == ServiceState.UNKNOWN

    async def test_query_nonexistent_service(self) -> None:
        mgr = WindowsServicesManager()
        status = await mgr.query("DefinitelyNotAService12345")
        # On non-Windows returns unknown
        assert status.state in (ServiceState.UNKNOWN, ServiceState.STOPPED)

    async def test_list_services(self) -> None:
        mgr = WindowsServicesManager()
        services = await mgr.list()
        assert isinstance(services, list)

    async def test_start_stop_on_non_windows(self) -> None:
        mgr = WindowsServicesManager()
        # On non-Windows these are no-ops that return True
        assert await mgr.start("AnyService") is True
        assert await mgr.stop("AnyService") is True
        assert await mgr.pause("AnyService") is True
        assert await mgr.continue_("AnyService") is True


@pytest.mark.offline
class TestJobObjects:
    """JobObjectManager tests."""

    async def test_create_job(self) -> None:
        mgr = JobObjectManager()
        limits = JobResourceLimits(
            cpu_rate=50,
            max_memory_mb=1024,
            max_active_processes=4,
        )
        job = await mgr.create("test-job", limits=limits)
        assert job.name == "test-job"
        assert job.limits.cpu_rate == 50
        assert job.limits.max_memory_mb == 1024
        assert job.state == JobState.ACTIVE
        assert job.process_count == 0

    async def test_assign_process(self) -> None:
        mgr = JobObjectManager()
        job = await mgr.create("test-assign")
        result = await mgr.assign_process(job.handle, 1234)
        assert result is True
        updated = await mgr.query(job.handle)
        assert updated.process_count == 1

    async def test_terminate_job(self) -> None:
        mgr = JobObjectManager()
        job = await mgr.create("test-terminate")
        await mgr.assign_process(job.handle, 100)
        await mgr.assign_process(job.handle, 200)
        result = await mgr.terminate(job.handle, exit_code=0)
        assert result is True
        updated = await mgr.query(job.handle)
        assert updated.state == JobState.TERMINATED
        assert updated.process_count == 0
        assert updated.terminated_process_count == 2

    async def test_close_job_with_kill_on_close(self) -> None:
        mgr = JobObjectManager()
        limits = JobResourceLimits(kill_on_job_close=True)
        job = await mgr.create("test-close-kill", limits=limits)
        await mgr.assign_process(job.handle, 999)
        await mgr.close(job.handle)
        updated = await mgr.query(job.handle)
        assert updated.state == JobState.CLOSED

    async def test_close_job_without_kill(self) -> None:
        mgr = JobObjectManager()
        limits = JobResourceLimits(kill_on_job_close=False)
        job = await mgr.create("test-close-nokill", limits=limits)
        await mgr.assign_process(job.handle, 999)
        await mgr.close(job.handle)
        updated = await mgr.query(job.handle)
        # Job should still be active (not killed) but marked as closed
        assert updated.state in (JobState.ACTIVE, JobState.CLOSED)

    async def test_find_by_name(self) -> None:
        mgr = JobObjectManager()
        await mgr.create("findable-job")
        found = await mgr.find_by_name("findable-job")
        assert found is not None
        assert found.name == "findable-job"
        not_found = await mgr.find_by_name("nope")
        assert not_found is None

    async def test_list_jobs(self) -> None:
        mgr = JobObjectManager()
        await mgr.create("job-a")
        await mgr.create("job-b")
        jobs = await mgr.list()
        assert len(jobs) == 2

    async def test_terminate_unknown_handle_raises(self) -> None:
        mgr = JobObjectManager()
        with pytest.raises(KeyError):
            await mgr.terminate(99999)


@pytest.mark.offline
class TestAppContainer:
    """AppContainerManager tests."""

    async def test_create_profile(self) -> None:
        mgr = AppContainerManager()
        profile = await mgr.create_profile(
            "agent-sandbox",
            capabilities=[SandboxCapability.INTERNET],
        )
        assert profile.name == "agent-sandbox"
        assert profile.sid.startswith("S-1-15-3-")
        assert SandboxCapability.INTERNET in profile.capabilities

    async def test_create_profile_invalid_capability(self) -> None:
        mgr = AppContainerManager()
        with pytest.raises(ValueError, match="Unknown capability"):
            await mgr.create_profile("bad", capabilities=["nonexistent"])

    async def test_create_duplicate_profile(self) -> None:
        mgr = AppContainerManager()
        await mgr.create_profile("dup")
        with pytest.raises(ValueError, match="already exists"):
            await mgr.create_profile("dup")

    async def test_delete_profile(self) -> None:
        mgr = AppContainerManager()
        await mgr.create_profile("deletable")
        assert await mgr.delete_profile("deletable") is True
        assert await mgr.delete_profile("deletable") is False

    async def test_launch_in_sandbox(self) -> None:
        mgr = AppContainerManager()
        await mgr.create_profile("launch-test")
        proc = await mgr.launch("launch-test", r"C:\agent.exe", ["--verbose"])
        assert proc.pid > 0
        assert proc.profile_name == "launch-test"
        assert proc.exe_path == r"C:\agent.exe"
        assert proc.args == ["--verbose"]
        assert proc.exited is False

    async def test_terminate_process(self) -> None:
        mgr = AppContainerManager()
        await mgr.create_profile("term-test")
        proc = await mgr.launch("term-test", "/bin/true")
        result = await mgr.terminate(proc.pid, exit_code=42)
        assert result is True
        procs = await mgr.list_processes()
        updated = next(p for p in procs if p.pid == proc.pid)
        assert updated.exited is True
        assert updated.exit_code == 42

    async def test_launch_unknown_profile(self) -> None:
        mgr = AppContainerManager()
        with pytest.raises(ValueError, match="not found"):
            await mgr.launch("nope", "/bin/true")

    async def test_wait_for_exit_timeout(self) -> None:
        mgr = AppContainerManager()
        await mgr.create_profile("wait-test")
        proc = await mgr.launch("wait-test", "/bin/sleep")
        # Process won't exit on its own → timeout
        result = await mgr.wait(proc.pid, timeout_s=0.3)
        assert result is None

    async def test_wait_for_exit_success(self) -> None:
        mgr = AppContainerManager()
        await mgr.create_profile("wait-success")
        proc = await mgr.launch("wait-success", "/bin/true")
        await mgr.terminate(proc.pid, exit_code=0)
        result = await mgr.wait(proc.pid, timeout_s=1.0)
        assert result == 0


@pytest.mark.offline
class TestWDAC:
    """WDAC policy tests."""

    async def test_create_policy(self) -> None:
        mgr = WDACManager()
        rules = [
            SignerRule(name="Microsoft", cert_thumbprint="ABC123"),
            FilePathRule(name="System32", path=r"%SystemRoot%\*", allowed=True),
        ]
        policy = await mgr.create_policy(
            "baseline",
            description="Default policy",
            rules=rules,
        )
        assert policy.name == "baseline"
        assert policy.state == PolicyState.DRAFT
        assert len(policy.rules) == 2

    async def test_sign_policy(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy("signable")
        signed = await mgr.sign_policy(policy.id, cert_thumbprint="DEF456")
        assert signed.state == PolicyState.SIGNED
        assert signed.signed_at is not None

    async def test_publish_policy_audit(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy("publishable")
        await mgr.sign_policy(policy.id, cert_thumbprint="XYZ")
        published = await mgr.publish_policy(policy.id, audit_mode=True)
        assert published.state == PolicyState.AUDIT
        assert published.enforced_at is not None

    async def test_publish_policy_enforce(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy("enforceable")
        await mgr.sign_policy(policy.id, cert_thumbprint="XYZ")
        published = await mgr.publish_policy(policy.id, audit_mode=False)
        assert published.state == PolicyState.ENFORCED

    async def test_revoke_policy(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy("revokable")
        await mgr.sign_policy(policy.id, cert_thumbprint="XYZ")
        await mgr.publish_policy(policy.id, audit_mode=True)
        revoked = await mgr.revoke_policy(policy.id)
        assert revoked.state == PolicyState.REVOKED

    async def test_add_rule_to_draft(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy("mutable")
        await mgr.add_rule(
            policy.id,
            PublisherRule(name="TrustedPub", publisher_cn="CN=AAiOS"),
        )
        updated = await mgr.get_policy(policy.id)
        assert updated is not None
        assert len(updated.rules) == 1

    async def test_cannot_modify_enforced_policy(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy("locked")
        await mgr.sign_policy(policy.id, cert_thumbprint="XYZ")
        await mgr.publish_policy(policy.id, audit_mode=False)
        with pytest.raises(RuntimeError, match="state"):
            await mgr.add_rule(
                policy.id,
                FilePathRule(name="extra", path="*"),
            )

    async def test_check_binary_allowed_by_signer(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy(
            "check",
            rules=[
                SignerRule(
                    name="Microsoft",
                    cert_thumbprint="ABC123",
                    allowed=True,
                ),
            ],
        )
        result = await mgr.check_binary(
            policy.id,
            r"C:\Windows\System32\cmd.exe",
            signer_thumbprint="ABC123",
        )
        assert result["allowed"] is True
        assert "Microsoft" in result["matched_rules"]

    async def test_check_binary_denied_no_match(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy(
            "deny",
            rules=[
                SignerRule(
                    name="Microsoft",
                    cert_thumbprint="ABC123",
                    allowed=True,
                ),
            ],
        )
        result = await mgr.check_binary(
            policy.id,
            r"C:\malware.exe",
            signer_thumbprint="ZZZ999",  # not in policy
        )
        assert result["allowed"] is False

    async def test_check_binary_filepath_match(self) -> None:
        mgr = WDACManager()
        policy = await mgr.create_policy(
            "path",
            rules=[
                FilePathRule(
                    name="System32",
                    path=r"C:\Windows\System32\*",
                    allowed=True,
                ),
            ],
        )
        result = await mgr.check_binary(
            policy.id,
            r"C:\Windows\System32\cmd.exe",
        )
        assert result["allowed"] is True
        assert "System32" in result["matched_rules"]

    async def test_list_policies(self) -> None:
        mgr = WDACManager()
        await mgr.create_policy("p1")
        await mgr.create_policy("p2")
        policies = await mgr.list_policies()
        assert len(policies) == 2


@pytest.mark.offline
class TestTaskScheduler:
    """TaskSchedulerManager tests."""

    async def test_create_task(self) -> None:
        mgr = TaskSchedulerManager()
        task = await mgr.create(
            "AAiOS-HealthCheck",
            actions=[
                TaskAction(
                    path=r"C:\AAiOS\agent.exe",
                    arguments="--health-check",
                    working_dir=r"C:\AAiOS",
                ),
            ],
            triggers=[
                TaskTrigger(
                    trigger_type=TriggerType.DAILY,
                    repetition_minutes=30,
                ),
            ],
            description="Periodic supervisor health check",
        )
        assert task.name == "AAiOS-HealthCheck"
        assert len(task.actions) == 1
        assert len(task.triggers) == 1
        assert task.enabled is True

    async def test_create_duplicate_task(self) -> None:
        mgr = TaskSchedulerManager()
        await mgr.create("dup-task", actions=[TaskAction(path="/bin/true")])
        with pytest.raises(ValueError, match="already exists"):
            await mgr.create("dup-task", actions=[TaskAction(path="/bin/true")])

    async def test_run_task(self) -> None:
        mgr = TaskSchedulerManager()
        await mgr.create("runnable", actions=[TaskAction(path="/bin/true")])
        result = await mgr.run("runnable")
        assert result is True
        task = await mgr.get("runnable")
        assert task.last_run_time is not None

    async def test_run_unknown_task(self) -> None:
        mgr = TaskSchedulerManager()
        with pytest.raises(ScheduledTaskNotFoundError):
            await mgr.run("nope")

    async def test_enable_disable(self) -> None:
        mgr = TaskSchedulerManager()
        await mgr.create("toggle", actions=[TaskAction(path="/bin/true")])
        assert await mgr.disable("toggle") is True
        task = await mgr.get("toggle")
        assert task.enabled is False
        assert await mgr.enable("toggle") is True
        task = await mgr.get("toggle")
        assert task.enabled is True

    async def test_delete_task(self) -> None:
        mgr = TaskSchedulerManager()
        await mgr.create("deletable", actions=[TaskAction(path="/bin/true")])
        assert await mgr.delete("deletable") is True
        assert await mgr.delete("deletable") is False

    async def test_list_tasks(self) -> None:
        mgr = TaskSchedulerManager()
        await mgr.create("t1", actions=[TaskAction(path="/bin/true")])
        await mgr.create("t2", actions=[TaskAction(path="/bin/true")])
        tasks = await mgr.list()
        assert len(tasks) == 2
