# AAiOS Production Deployment Manual
## Version 5.3.2 — Enterprise Deployment Guide

This guide provides instructions for deploying AAiOS in production environments.

---

### 1. Windows Service Deployment

AAiOS can run as a background Windows Service using NSSM (Non-Sucking Service Manager) or pywin32:
```powershell
# Register the service
aaios service install --name "AAiOS_Kernel"
# Start the service
aaios service start --name "AAiOS_Kernel"
```

### 2. Linux systemd Service Deployment

To deploy AAiOS as a systemd service on Linux:
1. Create a service file `/etc/systemd/system/aaios.service`:
   ```ini
   [Unit]
   Description=AAiOS Kernel Daemon
   After=network.target

   [Service]
   Type=simple
   User=aaios
   WorkingDirectory=/home/aaios/aaios
   ExecStart=/home/aaios/aaios/.venv/bin/aaios start
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
2. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable aaios
   sudo systemctl start aaios
   ```
