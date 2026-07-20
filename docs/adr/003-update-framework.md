# ADR-003: Provider-Based Update Framework

## Status
Accepted

## Context
The Desktop Runtime must support automatic updates without depending directly
on GitHub. The update system must be provider-agnostic, support multiple
channels, verify package integrity and signatures, and support silent install
with rollback on failure.

## Decision

### 1. Provider Contract
`UpdateProvider` is an abstract base class that defines `fetch_latest()`.
Every update source (GitHub Releases, enterprise CDN, local file share)
implements this interface. The framework never imports GitHub directly.

### 2. Release Channels
Five channels with configurable auto-update policies:
- STABLE: auto-check + auto-install
- LTS: auto-check + auto-install (opt-in)
- BETA: auto-check + notify only
- NIGHTLY: auto-check + notify only
- ENTERPRISE: off by default

### 3. Update Pipeline
1. Provider fetches manifest (channel-filtered)
2. VersionManager checks channel upgrade rules
3. Downloader streams package + computes SHA-256 inline
4. PackageVerifier checks integrity + signature
5. RollbackManager creates pre-update checkpoint
6. Migration runs (DB, config, plugins)
7. ReleaseValidator validates installation
8. On failure: automatic rollback

### 4. Integrity Verification
- SHA-256 computed during download
- Published checksum verified after download
- Digital signatures verified against registered verifier
- No signature verifier = deny-by-default

### 5. Rollback
The rollback system delegates to the existing BackupManager/RecoveryManager.
Pre-upgrade checkpoints are full backups tagged with the target version.
Checkpoints are released after successful upgrade.

## Consequences
- GitHub Releases is only the first provider implementation
- Enterprise users can implement custom providers
- Packages are cryptographically verified before install
- Failed updates never leave the system in an inconsistent state
- No breaking changes to existing update consumers
