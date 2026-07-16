# AAiOS Windows Administrator Guide
## Version 5.3.2 — Windows Integration

This guide provides Windows-specific instructions for administering AAiOS.

---

### 1. PowerShell Script Execution
Ensure execution policies allow script running:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

### 2. Windows Defender Integration
Exclude workspace folders to prevent false positives and scanning latency:
```powershell
Add-MpPreference -ExclusionPath "E:\AAIOS"
```
