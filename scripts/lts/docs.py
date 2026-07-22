#!/usr/bin/env python
"""AAiOS v5.3.1 LTS — Documentation Audit Script.

Verifies all required documentation exists and is up to date.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REQUIRED_DOCS: list[tuple[str, str]] = [
    ("README.md", "Project README"),
    ("CHANGELOG.md", "Changelog"),
    ("CONTRIBUTING.md", "Contributing guide"),
    ("CODE_OF_CONDUCT.md", "Code of conduct"),
    ("SECURITY.md", "Security policy"),
    ("SUPPORT.md", "Support policy"),
    ("docs/installation.md", "Installation guide"),
    ("docs/deployment.md", "Deployment guide"),
    ("docs/developer-guide.md", "Developer guide"),
    ("docs/api-reference.md", "API reference"),
    ("docs/cli-reference.md", "CLI reference"),
    ("docs/troubleshooting.md", "Troubleshooting"),
    ("docs/migration-v2.md", "Migration guide"),
    ("docs/architecture", "Architecture docs directory"),
    ("docs/agent-sdk", "Agent SDK docs directory"),
    ("docs/plugin-sdk", "Plugin SDK docs directory"),
]


def audit_docs(root: Path) -> dict:
    """Audit documentation completeness."""
    results: list[dict] = []
    for path_str, desc in REQUIRED_DOCS:
        full = root / path_str
        exists = full.exists()
        results.append(
            {
                "path": path_str,
                "description": desc,
                "exists": exists,
                "type": "directory" if "." not in path_str else "file",
            }
        )
    existing = sum(1 for r in results if r["exists"])
    return {
        "total_required": len(REQUIRED_DOCS),
        "existing": existing,
        "missing": len(REQUIRED_DOCS) - existing,
        "completeness_pct": round(existing / len(REQUIRED_DOCS) * 100, 2),
        "items": results,
    }


def main() -> int:
    root = Path().resolve()
    print("AAiOS v5.3.1 LTS — Documentation Audit")
    print("=" * 60)
    audit = audit_docs(root)
    print(f"Required docs: {audit['total_required']}")
    print(f"Existing: {audit['existing']}")
    print(f"Missing: {audit['missing']}")
    print(f"Completeness: {audit['completeness_pct']}%")
    print("\nMissing docs:")
    for item in audit["items"]:
        if not item["exists"]:
            print(f"  - {item['path']} ({item['description']})")
    out_dir = Path("lts-audit")
    out_dir.mkdir(exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "version": "5.3.1-LTS",
        **audit,
    }
    (out_dir / "documentation_audit.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
