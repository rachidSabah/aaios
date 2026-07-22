# Installer Guide

> Version 1.0.0-rc1

## Windows Installation

### MSI Installer

Download the MSI package from the GitHub Releases page and run it:

```powershell
msiexec /i aaios-desktop-1.0.0-rc1.msi /qb
```

### EXE Installer

```powershell
.\aaios-desktop-1.0.0-rc1.exe /SILENT
```

### Portable ZIP

```powershell
# Extract anywhere and run
Expand-Archive -Path aaios-desktop-1.0.0-rc1.zip -DestinationPath C:\AAiOS
cd C:\AAiOS
.\aaios.exe desktop
```

## Installation Layout

```
C:\Program Files\AAiOS\           # Application binaries
  ├── aaios.exe                   # Main executable
  ├── core/                       # Python core libraries
  ├── services/                   # Python service modules
  └── desktop/                    # Desktop shell assets

%APPDATA%\AAiOS\                  # User data
  ├── config.yaml                 # User configuration
  ├── desktop/                    # Desktop runtime data
  │   ├── db/                     # Local database
  │   ├── crashes/                # Crash reports
  │   ├── plugins/                # Installed plugins
  │   └── offline/                # Offline sync queue
  └── logs/                       # Application logs
```

## Command Line

```bash
aaios desktop start               # Start Desktop Runtime
aaios desktop stop                # Stop Desktop Runtime
aaios desktop status              # Check runtime status
aaios desktop diagnostics          # Run diagnostics
```

## Updating

```bash
aaios update                      # Check + install updates
aaios update --check              # Just check
```

## Uninstalling

### Windows
```powershell
# Control Panel > Programs > AAiOS > Uninstall
# Or:
msiexec /x aaios-desktop-1.0.0-rc1.msi /qb
```

### CLI
```bash
aaios uninstall                   # Keep user data
aaios uninstall --remove-data     # Remove everything
```
