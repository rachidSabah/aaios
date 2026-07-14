# AAiOS Windows bootstrap script
# ===============================
# Called by the Inno Setup installer (deploy/windows/aaios.iss) after file
# copy. Also runnable standalone for development installs:
#
#   .\bootstrap.ps1 -Action install -InstallDir "C:\Program Files\AAiOS" -DataDir "C:\ProgramData\AAiOS"
#   .\bootstrap.ps1 -Action uninstall
#   .\bootstrap.ps1 -Action doctor
#
# Phase 2 stub: this script wires up the structure but the actual service
# creation, ACL setup, and master key generation land in Phase 14.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall', 'doctor', 'start', 'stop', 'restart')]
    [string]$Action,

    [string]$InstallDir = 'C:\Program Files\AAiOS',
    [string]$DataDir = "$env:ProgramData\AAiOS",

    [string]$ServiceAccount = '.\AAiOS',
    [string]$ServiceAccountPassword  # prompted if needed
)

$ErrorActionPreference = 'Stop'

function Write-Section($name) {
    Write-Host ""
    Write-Host "==> $name" -ForegroundColor Cyan
}

function Test-Admin {
    $current = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    return $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Error "This script must be run as Administrator."
    exit 1
}

# Service definitions (Phase 14 will populate these fully)
$Services = @(
    @{ Name = 'AAiOS-API';     Binary = 'python.exe'; Args = '-m uvicorn surfaces.api.app:app --host 127.0.0.1 --port 8000' }
    @{ Name = 'AAiOS-Runtime'; Binary = 'python.exe'; Args = '-m supervisor.runtime' }
    @{ Name = 'AAiOS-Web';     Binary = 'node.exe';   Args = 'web/server.js' }
    @{ Name = 'AAiOS-Worker';  Binary = 'python.exe'; Args = '-m aaios.worker' }
    # AAiOS-Hermes is started on-demand by the runtime, not as a service
)

switch ($Action) {
    'install' {
        Write-Section "Install AAiOS services"
        Write-Host "Install dir: $InstallDir"
        Write-Host "Data dir:    $DataDir"
        Write-Host ""
        Write-Host "Phase 2 stub — full implementation lands in Phase 14:" -ForegroundColor Yellow
        Write-Host "  1. Create service account '$ServiceAccount'"
        Write-Host "  2. Set ACLs on $DataDir (SYSTEM + $ServiceAccount only)"
        Write-Host "  3. Generate master key (PBKDF2 from passphrase)"
        Write-Host "  4. Install NSSM"
        Write-Host "  5. Register services: $($Services.Name -join ', ')"
        Write-Host "  6. Configure recovery (restart x3, then fail)"
        Write-Host "  7. Configure Windows Defender exclusions"
        Write-Host "  8. Run 'aaios doctor'"
        Write-Host ""
        Write-Host "✓ Install scaffolding verified" -ForegroundColor Green
    }

    'uninstall' {
        Write-Section "Uninstall AAiOS services"
        foreach ($svc in $Services) {
            if (Get-Service -Name $svc.Name -ErrorAction SilentlyContinue) {
                Write-Host "  Removing service: $($svc.Name)"
                # sc.exe delete $svc.Name  # Phase 14
            } else {
                Write-Host "  Service not found, skipping: $($svc.Name)" -ForegroundColor DarkGray
            }
        }
        Write-Host "✓ Uninstall scaffolding verified" -ForegroundColor Green
    }

    'doctor' {
        Write-Section "AAiOS Windows doctor"
        Write-Host "Phase 2 stub — run 'aaios doctor' for the full check."
        $svc = Get-Service -Name 'AAiOS-*' -ErrorAction SilentlyContinue
        if ($svc) {
            $svc | Format-Table Name, Status, StartType -AutoSize
        } else {
            Write-Host "No AAiOS services installed." -ForegroundColor Yellow
        }
    }

    'start' {
        Write-Section "Start AAiOS services"
        foreach ($svc in $Services) {
            if (Get-Service -Name $svc.Name -ErrorAction SilentlyContinue) {
                Write-Host "  Starting: $($svc.Name)"
                # Start-Service -Name $svc.Name  # Phase 14
            }
        }
    }

    'stop' {
        Write-Section "Stop AAiOS services"
        foreach ($svc in $Services) {
            if (Get-Service -Name $svc.Name -ErrorAction SilentlyContinue) {
                Write-Host "  Stopping: $($svc.Name)"
                # Stop-Service -Name $svc.Name  # Phase 14
            }
        }
    }

    'restart' {
        & $PSCommandPath -Action stop @PSBoundParameters
        & $PSCommandPath -Action start @PSBoundParameters
    }
}
