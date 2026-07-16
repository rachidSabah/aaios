# AAiOS Provider Integration Guide
## Version 5.3.2 — Provider Extensions

This guide describes how to configure model provider integrations in AAiOS.

---

### 1. Configuration Setup

Configure provider credentials in `config/config.yaml`:
```yaml
providers:
  openai:
    api_key: "sk-..."
  anthropic:
    api_key: "sk-ant-..."
```

### 2. Credential Encryption
Provider credentials are encrypted at rest using a Fernet key stored securely in the local environment.
