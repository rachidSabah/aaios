# Update Framework Guide

> Version 1.0.0-rc1

## Overview

The Update Framework is a provider-based system for automatic software updates.
It is designed to be GitHub-agnostic — GitHub Releases is the first provider
implementation, but the framework works with any source that implements the
`UpdateProvider` contract.

## Architecture

```
                    ┌─────────────────────┐
                    │   UpdateProvider     │ (abstract)
                    │  ─────────────────   │
                    │  fetch_latest()      │
                    └────────┬────────────┘
                             │
             ┌───────────────┼───────────────┐
             ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │    GitHub    │ │  Enterprise  │ │ Custom/S3/CDN│
    │   Releases   │ │    Server    │ │     etc.     │
    └──────────────┘ └──────────────┘ └──────────────┘
             │               │               │
             └───────────────┼───────────────┘
                             ▼
                    ┌─────────────────────┐
                    │    UpdateManager     │
                    │  check_for_updates() │
                    │  install_update()    │
                    └────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ Downloader │ │ Verifier   │ │ Rollback   │
     │ (SHA-256)  │ │ (Integrity │ │ Manager    │
     │            │ │ + Sig)     │ │            │
     └────────────┘ └────────────┘ └────────────┘
```

## Release Channels

| Channel | Policy (Default) | Description |
|---------|------------------|-------------|
| STABLE  | AUTO | Production releases |
| LTS     | AUTO (opt-in) | Long-term support |
| BETA    | NOTIFY | Pre-release candidates |
| NIGHTLY | NOTIFY | Daily builds |
| ENTERPRISE | OFF | Enterprise releases |

### Policies
- **AUTO**: Check + install automatically (silent)
- **NOTIFY**: Check + notify user, install on action
- **OFF**: Never check this channel

## Update Pipeline

1. **Check**: Provider fetches latest manifest for enabled channels
2. **Version Compare**: VersionManager checks if it's a genuine upgrade
3. **Download**: Package streamed to disk with inline SHA-256 computation
4. **Verify**: SHA-256 integrity check + optional digital signature verification
5. **Checkpoint**: Full backup via RollbackManager
6. **Migrate**: Database migrations, config merge, plugin updates
7. **Validate**: ReleaseValidator checks installation integrity
8. **Cleanup**: On success, checkpoint released; on failure, automatic rollback

## Manual Usage

### Python API

```python
from services.update.manager import UpdateManager
from services.update.github_provider import GitHubReleaseProvider

mgr = UpdateManager(current_version="1.0.0-rc1")
mgr.register_provider(GitHubReleaseProvider(repo="rachidSabah/aaios"))

# Check for updates
info = await mgr.check_for_updates()
if info:
    print(f"Update available: {info.version}")

# Install
report = await mgr.install_update(info)
print(f"Status: {report.status.value}")
```

### CLI

```bash
aaios update                   # check + install
aaios update --check           # just check
aaios update --channel beta    # check beta channel
aaios pin-version 1.0.0        # pin to specific version
```

## Custom Provider Implementation

```python
from services.update.provider import UpdateProvider, UpdateManifest
from services.update.models import ReleaseChannel

class MyCustomProvider(UpdateProvider):
    @property
    def name(self) -> str:
        return "my-custom-provider"

    async def fetch_latest(self, channel, *, current_version, timeout_s=10.0):
        # Fetch from your own source
        # Return UpdateManifest or None
        ...

# Register with the manager
mgr.register_provider(MyCustomProvider())
```
