"""AAiOS Windows Native Service — Windows-specific capabilities.

Submodules:
  - services: Windows Services (install/start/stop/query via sc.exe)
  - job_objects: Job Objects (process groups with resource limits)
  - appcontainer: AppContainer sandboxing (capability-based isolation)
  - wdac: Windows Defender Application Control (code integrity policies)
  - task_scheduler: Task Scheduler (scheduled tasks via schtasks.exe)

Every module degrades gracefully on non-Windows platforms: methods return
structured "unsupported" results so the rest of AAiOS can be developed
and tested on Linux/WSL.
"""

from __future__ import annotations

from services.windows_native.appcontainer import (
    AppContainerManager,
    AppContainerProcess,
    AppContainerProfile,
    SandboxCapability,
)
from services.windows_native.job_objects import (
    JobHandle,
    JobLimitExceededError,
    JobObject,
    JobObjectManager,
    JobResourceLimits,
    JobState,
)
from services.windows_native.services import (
    ServiceAlreadyExistsError,
    ServiceConfig,
    ServiceNotFoundError,
    ServiceState,
    ServiceStatus,
    WindowsServicesManager,
)
from services.windows_native.task_scheduler import (
    ScheduledTask,
    ScheduledTaskNotFoundError,
    TaskAction,
    TaskSchedulerManager,
    TaskState,
    TaskTrigger,
    TriggerType,
)
from services.windows_native.wdac import (
    FilePathRule,
    PolicyState,
    PolicyViolationError,
    PublisherRule,
    SignerRule,
    WDACManager,
    WDACPolicy,
    WDACRule,
)

__all__ = [
    "AppContainerManager",
    "AppContainerProfile",
    "AppContainerProcess",
    "FilePathRule",
    "JobHandle",
    "JobLimitExceededError",
    "JobObject",
    "JobObjectManager",
    "JobResourceLimits",
    "JobState",
    "PolicyState",
    "PolicyViolationError",
    "PublisherRule",
    "SandboxCapability",
    "ScheduledTask",
    "ScheduledTaskNotFoundError",
    "ServiceAlreadyExistsError",
    "ServiceConfig",
    "ServiceNotFoundError",
    "ServiceState",
    "ServiceStatus",
    "SignerRule",
    "TaskAction",
    "TaskSchedulerManager",
    "TaskState",
    "TaskTrigger",
    "TriggerType",
    "WDACManager",
    "WDACPolicy",
    "WDACRule",
    "WindowsServicesManager",
]
