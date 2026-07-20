# ADR-005: Installer Architecture

## Status
Accepted

## Context
Production packaging for the Desktop Runtime must produce Windows MSI, EXE,
and Portable ZIP artifacts. The architecture must prepare for future Linux
(AppImage, DEB, RPM) and macOS (DMG, PKG) package formats without redesign.

## Decision

### 1. Tauri Shell for Desktop
The desktop shell uses Tauri 2, which provides:
- Native WebView2 rendering on Windows
- Native system tray API
- Native notification API
- Secure IPC between Rust backend and web frontend
- Window state persistence
- Deep linking support
- Auto-updater integration

### 2. Platform-Independent Core
The Tauri shell is a thin wrapper. All business logic lives in the Python
services layer. Tauri commands delegate to the FastAPI backend via HTTP
or the Event Bus.

### 3. Packaging Strategy
- **MSI**: Tauri bundler produces Windows Installer
- **EXE**: Tauri bundler produces self-contained installer
- **Portable ZIP**: Standalone distribution with embedded Python runtime
- **Future formats**: Adapter architecture via Tauri's bundler plugins

### 4. Auto-Update
The Tauri updater is configured as a fallback. The primary update system
is the provider-based Update Framework, which supports custom providers
and full integrity verification.

### 5. Desktop Data Directory
All desktop runtime data is stored under:
- Windows: `%APPDATA%\AAiOS\desktop\`
- Linux: `~/.local/share/aaios/desktop/`
- macOS: `~/Library/Application Support/AAiOS/desktop/`

## Consequences
- MSI and EXE packages are producible from a single build pipeline
- Linux/macOS packaging requires only Tauri configuration changes
- The Python backend is packaged as a PyInstaller executable within the bundle
- Auto-updates work through both Tauri and the provider framework
