# AAiOS Release Packaging Guide
## Version 5.3.2 — Enterprise Release Engineering

This guide details the release packaging subsystem responsible for generating portable, zip, developer, and offline installer packages, alongside Software Bills of Materials (SBOM) and cryptographic manifests.

---

### 1. Release Packaging Subsystem

The packaging engine bundles AAiOS source layers, environment bootstrapper hooks, and package manager modules.
*   **Target Location**: Releases are generated in the `releases/` workspace folder.
*   **Command**: `aaios package --version <version>`

### 2. Supported Packaging Formats

| Format | Output Target | Included Components | Target Use Case |
| :--- | :--- | :--- | :--- |
| **Portable** | `aaios-portable-v5.3.2.zip` | Full codebase + `.venv` boot scrapers | Zero-config, sandboxed runtimes |
| **Standard Zip** | `aaios-zip-v5.3.2.zip` | Code repository source | Standard git clone / source distribution |
| **Developer** | `aaios-developer-v5.3.2.zip` | Codebase + unit/integration test suites | Extension developers and plugin authors |
| **Offline Installer** | `aaios-offline_installer-v5.3.2.zip` | Code + dependency caches (wheel house, pnpm stores) | Air-gapped, secure server rooms |
| **Enterprise** | `aaios-enterprise-v5.3.2.zip` | Code + security policies (WDAC, AppContainer setup) | Strict enterprise governance |

### 3. Release Manifest & SBOM Specifications

Every package operation compiles a structured manifest file:
*   **Release Manifest (`releases/release-manifest.json`)**: Contains timestamps, package versioning, file sizes, and matching SHA-256 and SHA-512 hashes.
*   **SBOM (`releases/sbom.json`)**: Formatted as CycloneDX JSON (v1.5 spec), documenting active libraries, dependencies, license declarations, and hashes.

---

### 4. Step-by-Step Build Pipeline

1.  **Dependency Collection**: Gathers exact version details from the active Python virtual environment and `package.json`.
2.  **License Scraping**: Validates that all library licenses meet enterprise clearance criteria (e.g. MIT, Apache-2.0, BSD).
3.  **Archive Compression**: Packages the respective file configurations using DEFLATE compression.
4.  **Checksum Generation**: Generates SHA-256 and SHA-512 integrity verification keys.
5.  **Manifest Export**: Writes the output manifest and CycloneDX-compatible SBOM file.
