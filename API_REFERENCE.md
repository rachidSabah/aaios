# AAiOS REST API Reference Manual
## Version 5.3.2 — OpenAPI Schema

AAiOS exposes a REST API via FastAPI, enabling programmatical integration with dashboards and external services.

---

### 1. Health Endpoints

*   **`GET /healthz`**: Check API status.
*   **`GET /api/v1/doctor`**: Query diagnostic checks and active issues list.

### 2. Backup Endpoints

*   **`POST /api/v1/backup`**: Start a new backup.
*   **`POST /api/v1/backup/restore/{id}`**: Trigger a restore.
