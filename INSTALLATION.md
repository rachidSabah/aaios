# AAiOS Installation Manual
## Version 5.3.2 — Enterprise Deployment

This document outlines the procedures for installing and bootstrapping AAiOS on Windows and Linux.

---

### 1. Windows 11 Installation (One-Click)

Run the following command in an administrator PowerShell prompt:
```powershell
irm https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/windows/install.ps1 | iex
```

### 2. Linux / WSL2 Installation (One-Click)

Run the following command in a terminal:
```bash
curl -fsSL https://raw.githubusercontent.com/rachidSabah/aaios/main/deploy/linux/install.sh | bash
```

---

### 3. Manual Installation
If you prefer a manual setup:
1. Clone the repository:
   ```bash
   git clone https://github.com/rachidSabah/aaios.git
   cd aaios
   ```
2. Run the bootstrapper script:
   ```powershell
   .\tasks.ps1 install
   ```
3. Start AAiOS services:
   ```powershell
   aaios start
   ```
