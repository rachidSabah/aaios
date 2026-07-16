# AAiOS Linux Administrator Guide
## Version 5.3.2 — Linux & WSL2 Integration

This guide provides Linux-specific instructions for administering AAiOS.

---

### 1. Installation Requirements
Ensure python venv libraries are installed:
```bash
sudo apt-get install python3-venv python3-pip -y
```

### 2. System Throttling
Set process limits in `/etc/security/limits.conf` to configure high concurrency limits.
