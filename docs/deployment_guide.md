# AAiOS Enterprise Deployment Guide

This document guides system administrators through deploying the Agentic AI Operating System (AAIOS) on Windows and Windows Server environments.

---

## 1. System Requirements

*   **Operating System**: Windows 10 or Windows Server 2019/2022 (64-bit).
*   **Python**: Version 3.12.x.
*   **Node.js**: Version 18.x or 20.x.
*   **pnpm**: Version 8.x or higher.
*   **Hard Drive**: SSD with at least 10 GB free space.

---

## 2. Pre-Deployment Configuration

Set the following environment variables on the host system to configure runtime parameters:

```powershell
# Set environment to production
[System.Environment]::SetEnvironmentVariable("AAIOS_ENV", "production", "Machine")

# Configure LLM API Keys
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "Machine")
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "Machine")
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIza...", "Machine")
```

---

## 3. Installation Steps

### Step 1: Set PowerShell Execution Policy
Open PowerShell as an Administrator and enable script execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

### Step 2: Clone the Repository
Clone the enterprise release branch:
```bash
git clone https://github.com/rachidSabah/aaios E:\AAIOS
cd E:\AAIOS
```

### Step 3: Run the Task Installer
Execute the installation task. This automatically creates the python virtual environment (`.venv`), installs pip packages, and resolves node packages using pnpm:
```powershell
.\tasks.ps1 install
```

> [!NOTE]
> The installation script automatically injects `$env:NODE_OPTIONS = '--no-deprecation'` to bypass PowerShell NativeCommandErrors caused by Node.js warning outputs.

### Step 4: Bootstrap Workspace and Databases
Initialize all folders and sqlite databases:
```bash
.venv\Scripts\python -m surfaces.cli doctor --scan quick --heal --yes
```

### Step 5: Verify the Build
Run validation tests to confirm compliance:
```bash
.venv\Scripts\python -m surfaces.cli validate
```
Ensure that status reads `CERTIFIED`.

---

## 4. Troubleshooting Windows Deployments

### Issue: PowerShell native command execution fails on pnpm
*   **Symptom**: Stderr warnings (such as `url.parse()` deprecation) are intercepted as a script-terminating `NativeCommandError`.
*   **Solution**: Silence deprecation warnings in the current session:
    ```powershell
    $env:NODE_OPTIONS = '--no-deprecation'
    ```
    This bypasses warning interceptors.
