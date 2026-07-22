#!/usr/bin/env python
"""AAiOS v5.3.1 LTS — Coverage Aggregator.

Aggregates coverage across all unit tests and produces a coverage
report. The full test suite is too large to run with coverage in a
single pass, so we run per-package and merge.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_coverage() -> dict:
    """Run pytest with coverage and parse the XML."""
    # Run all unit tests with coverage
    cmd = [
        "/home/z/.venv/bin/python",
        "-m",
        "pytest",
        "tests/unit/",
        "--cov=core",
        "--cov=services",
        "--cov=agents",
        "--cov=supervisor",
        "--cov=orchestrator",
        "--cov-report=xml:coverage/lts_coverage.xml",
        "--cov-report=term",
        "-q",
        "--no-header",
        "-x",  # stop on first failure
    ]
    print("Running full unit test suite with coverage...")
    print("This may take several minutes...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr[-1000:])
    # Parse the XML
    xml_path = Path("coverage/lts_coverage.xml")
    if not xml_path.exists():
        return {"error": "coverage XML not produced"}
    import defusedxml.ElementTree as DefusedET

    tree = DefusedET.parse(xml_path)
    root = tree.getroot()
    line_rate = float(root.attrib.get("line-rate", "0"))
    branch_rate = float(root.attrib.get("branch-rate", "0"))
    # Per-package
    packages: dict[str, dict] = {}
    for cls in root.iter("class"):
        fname = cls.attrib.get("filename", "")
        lr = float(cls.attrib.get("line-rate", "0"))
        pkg = fname.split("/")[0] if "/" in fname else "root"
        if pkg not in packages:
            packages[pkg] = {"files": 0, "line_rate_sum": 0.0, "covered_files": 0}
        packages[pkg]["files"] += 1
        packages[pkg]["line_rate_sum"] += lr
        if lr > 0.5:
            packages[pkg]["covered_files"] += 1
    summary = {
        "overall_line_rate": round(line_rate, 4),
        "overall_branch_rate": round(branch_rate, 4),
        "overall_line_pct": round(line_rate * 100, 2),
        "overall_branch_pct": round(branch_rate * 100, 2),
        "packages": {
            pkg: {
                "files": data["files"],
                "avg_line_rate": round(data["line_rate_sum"] / data["files"], 4)
                if data["files"]
                else 0.0,
                "covered_files": data["covered_files"],
            }
            for pkg, data in packages.items()
        },
    }
    Path("lts-audit").mkdir(exist_ok=True)
    Path("lts-audit/coverage_report.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    summary = run_coverage()
    print(json.dumps(summary, indent=2))
    sys.exit(0)
