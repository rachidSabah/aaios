# AAiOS Best Practices Guide
## Version 5.3.2 — Best Practices

This guide provides recommendations for operating AAiOS in production environments.

---

### 1. Security Best Practices
*   **Credential Rotation**: Regularly rotate API keys and Fernet symmetric encryption keys.
*   **Restrict File Permissions**: Keep the `secrets/` directory permissions restricted.

### 2. Performance Tuning
*   **Database Placement**: Deploy database files on SSD storage to minimize transaction latency.
*   **Clean Regularly**: Run `aaios cleanup` weekly to reclaim disk space.
