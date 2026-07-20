#!/usr/bin/env pwsh
<#
.SYNOPSIS
    AAiOS v1.0.0-rc1 — Desktop Runtime Release Script
.DESCRIPTION
    Creates GitHub Release with packaging artifacts.
    Prerequisites: gh CLI (https://cli.github.com/)
#>

$ErrorActionPreference = "Stop"
$Repo = "rachidSabah/aaios"
$Tag = "v1.0.0-rc1"
$Title = "AAiOS v1.0.0-rc1 — Desktop Runtime"

# Ensure gh CLI is available
if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is required. Install from https://cli.github.com/"
    exit 1
}

Write-Host "=== AAiOS Release: $Tag ===" -ForegroundColor Cyan

# 1. Verify tag exists
git tag -l $Tag | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Tag $Tag not found locally. Run: git tag $Tag && git push origin $Tag"
    exit 1
}

# 2. Generate release notes
$ReleaseNotes = @"
## AAiOS v1.0.0-rc1 — Desktop Runtime

Phase 4, Milestone 6 complete. Production-quality native desktop application with full offline capability, local AI runtime, automatic update framework, native integrations, and Mission Control dashboard.

### Desktop Runtime (15 Services)
- **DesktopRuntimeManager** — lifecycle orchestrator for all desktop services
- **WindowManager** — multi-window state tracking with docking zones
- **WorkspaceManager** — named workspaces with persistent JSON layout
- **NativeNotificationService** — event-driven desktop notifications
- **SystemTray** — platform-abstracted system tray icon and menu
- **OfflineRuntimeManager** — connectivity monitoring + sync queue
- **LocalAIRuntimeManager** — local engine discovery (Ollama, llama.cpp, LocalAI)
- **PerformanceMonitor** — real CPU/memory/disk metrics via psutil
- **DiagnosticsManager** — health checks (Python, disk, event bus, platform)
- **CrashReporter** — exception capture, persistence, resolve workflow
- **DesktopPluginLoader** — zip-based install, hot-reload, manifest management
- **NativeCredentialStore** — Windows Credential Manager + encrypted file fallback
- **DesktopUpdater** — bridges Update Framework to desktop UI
- **BackgroundServiceRunner** — periodic maintenance task scheduler
- **LocalDatabaseManager** — embedded SQLite with SQLAlchemy + aiosqlite

### REST API (22 Endpoints)
Available under /api/v1/desktop/
- status, diagnostics, perfmon, perfmon/history, offline, local-ai
- notifications, windows, workspaces, plugins, logs, updates
- updates/check, credentials, system, services

### Update Framework
- Provider-based architecture (GitHub-agnostic)
- GitHubReleaseProvider as first implementation
- 5 release channels (STABLE, LTS, BETA, NIGHTLY, ENTERPRISE)
- SHA-256 integrity verification + digital signature support
- Automatic rollback via BackupManager
- Background update service with configurable intervals

### Documentation
- Desktop Runtime Guide (docs/desktop_runtime_guide.md)
- Offline Mode Guide (docs/offline_guide.md)
- Update Framework Guide (docs/update_framework_guide.md)
- Native API Guide (docs/native_api_guide.md)
- Installer Guide (docs/installer_guide.md)
- 5 Architecture Decision Records (docs/adr/)

### Files Changed
32 files changed, 3,987 insertions(+), 24 deletions(-)
"@

# 3. Create release (without artifacts - they are built separately)
Write-Host "Creating GitHub Release..." -ForegroundColor Yellow
gh release create $Tag `
    --title $Title `
    --notes $ReleaseNotes `
    --repo $Repo

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Release $Tag created successfully!" -ForegroundColor Green

    # 4. Upload artifacts (if they exist)
    $artifacts = @(
        "dist/aaios-desktop-$Tag.msi",
        "dist/aaios-desktop-$Tag.exe",
        "dist/aaios-desktop-$Tag.zip"
    )
    $existingArtifacts = $artifacts | Where-Object { Test-Path $_ }
    if ($existingArtifacts.Count -gt 0) {
        Write-Host "Uploading artifacts..." -ForegroundColor Yellow
        gh release upload $Tag $existingArtifacts --repo $Repo
        Write-Host "✓ Artifacts uploaded!" -ForegroundColor Green
    } else {
        Write-Host "No build artifacts found at dist/. Build them first with build.ps1" -ForegroundColor Yellow
    }
} else {
    Write-Error "Release creation failed"
    exit 1
}
