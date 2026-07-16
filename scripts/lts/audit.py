#!/usr/bin/env python
"""AAiOS v5.3.1 LTS — Repository Audit Script.

Performs a complete repository audit and emits three reports:
  - Repository Audit Report (architecture invariants, layering, dead code,
    duplicates, unused APIs, unreachable code, deprecated interfaces)
  - Technical Debt Report (TODOs, FIXMEs, placeholders, commented code,
    suppressions, skipped tests)
  - Dependency Graph + Architecture Compliance Report

Usage:
    python scripts/lts/audit.py [--root PATH] [--out-dir PATH]

Exit code 0 = audit ran successfully (does NOT imply zero findings).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AuditFinding:
    """A single audit finding."""
    category: str
    severity: str  # info | low | medium | high | critical
    file: str
    line: int
    description: str
    recommendation: str = ""


@dataclass
class AuditReport:
    """Complete audit report."""
    generated_at: str
    root: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------


class RepositoryAuditor:
    """Phase 1 — Repository Auditor."""

    # Layers in dependency order (lower = more foundational)
    LAYERS: tuple[tuple[str, str], ...] = (
        ("core", "Core kernel — no inbound deps from services/surfaces"),
        ("services", "Service layer — may import core only"),
        ("agents", "Agent implementations — may import core/services"),
        ("supervisor", "Supervisor — may import core/services/agents"),
        ("orchestrator", "Orchestrator — may import core/services/agents/supervisor"),
        ("surfaces", "Surfaces (CLI/API/Web) — may import everything"),
    )

    LAYER_ORDER: dict[str, int] = {name: i for i, (name, _) in enumerate(LAYERS)}

    # Banned imports outside core/gateway (INV-02)
    BANNED_IO_IMPORTS: tuple[str, ...] = (
        "import subprocess",
        "from subprocess",
        "import socket",
        "from socket",
        "import requests",
        "from requests",
    )

    # Noise directories to skip
    SKIP_DIRS: frozenset[str] = frozenset({
        ".venv", "node_modules", ".git", "__pycache__",
        "build", "dist", ".next", ".mypy_cache", ".ruff_cache",
        "coverage", "site",
    })

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.findings: list[AuditFinding] = []

    # --- public API -----------------------------------------------------

    def audit(self) -> AuditReport:
        """Run the complete audit."""
        self._audit_architecture_invariants()
        self._audit_layering()
        self._audit_dependency_graph()
        self._audit_circular_imports()
        self._audit_dead_code()
        self._audit_duplicate_logic()
        self._audit_unused_apis()
        self._audit_unreachable_code()
        self._audit_deprecated_interfaces()
        self._audit_security_issues()
        self._audit_performance_bottlenecks()
        return self._build_report()

    # --- architecture invariants ---------------------------------------

    def _audit_architecture_invariants(self) -> None:
        """INV-02: no I/O imports outside core/gateway/.
        INV-09: no agent implementation names in core/services/supervisor.
        """
        # INV-02
        for pkg in ("core", "services", "agents", "supervisor", "orchestrator", "surfaces"):
            pkg_dir = self.root / pkg
            if not pkg_dir.exists():
                continue
            for py in pkg_dir.rglob("*.py"):
                if any(seg in py.parts for seg in self.SKIP_DIRS):
                    continue
                if "gateway" in py.parts or "model_router" in py.parts:
                    continue
                if "surfaces" in py.parts and "cli" in py.parts:
                    continue
                try:
                    text = py.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    for banned in self.BANNED_IO_IMPORTS:
                        if banned in stripped:
                            self.findings.append(AuditFinding(
                                category="INV-02_violation",
                                severity="high",
                                file=str(py.relative_to(self.root)),
                                line=i,
                                description=f"Banned I/O import: {stripped}",
                                recommendation="Move I/O to core/gateway/ or use the existing gateway.",
                            ))
                            break

        # INV-09: agent implementation names in core/services/supervisor
        agent_names = ("ClaudeCode", "Hermes", "OpenHands", "Cline", "RooCode", "GeminiCLI", "CodexCLI")
        for pkg in ("core", "services", "supervisor", "orchestrator"):
            pkg_dir = self.root / pkg
            if not pkg_dir.exists():
                continue
            for py in pkg_dir.rglob("*.py"):
                if any(seg in py.parts for seg in self.SKIP_DIRS):
                    continue
                try:
                    text = py.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    for name in agent_names:
                        if name in line and not line.strip().startswith("#"):
                            # Allow in comments and string literals minimally
                            if "test_" in py.name:
                                continue
                            self.findings.append(AuditFinding(
                                category="INV-09_violation",
                                severity="medium",
                                file=str(py.relative_to(self.root)),
                                line=i,
                                description=f"Agent implementation name '{name}' referenced in core layer",
                                recommendation="Use the generic Agent protocol instead of concrete names.",
                            ))

    # --- layering -------------------------------------------------------

    def _audit_layering(self) -> None:
        """Verify layer dependency direction."""
        for py in self._python_files():
            rel = py.relative_to(self.root)
            parts = rel.parts
            if len(parts) < 2:
                continue
            current_layer = parts[0]
            if current_layer not in self.LAYER_ORDER:
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._check_layer_import(current_layer, alias.name, py, node.lineno)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self._check_layer_import(current_layer, node.module, py, node.lineno)

    def _check_layer_import(
        self, current_layer: str, imported_module: str, py: Path, line: int
    ) -> None:
        """Check if a layer imports from a higher layer."""
        top = imported_module.split(".", maxsplit=1)[0]
        if top not in self.LAYER_ORDER:
            return
        if self.LAYER_ORDER[top] > self.LAYER_ORDER[current_layer]:
            self.findings.append(AuditFinding(
                category="layer_violation",
                severity="high",
                file=str(py.relative_to(self.root)),
                line=line,
                description=f"Layer '{current_layer}' imports from higher layer '{top}'",
                recommendation=f"Reverse the dependency: {top} should depend on {current_layer}, not vice versa.",
            ))

    # --- dependency graph ----------------------------------------------

    def _audit_dependency_graph(self) -> None:
        """Build a module dependency graph and check for issues."""
        graph: dict[str, set[str]] = defaultdict(set)
        for py in self._python_files():
            rel = str(py.relative_to(self.root))[:-3].replace("/", ".")
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        graph[rel].add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        graph[rel].add(node.module)
        self._dep_graph = dict(graph)

    # --- circular imports ----------------------------------------------

    def _audit_circular_imports(self) -> None:
        """Detect circular import chains."""
        graph = getattr(self, "_dep_graph", {})
        if not graph:
            return
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            if node in rec_stack:
                cycle_start = path.index(node) if node in path else 0
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor in graph:
                    dfs(neighbor, path + [node])
            rec_stack.discard(node)

        for module in graph:
            if module not in visited:
                dfs(module, [])

        # Only report internal cycles (within first-party packages)
        first_party = {"core", "services", "agents", "supervisor", "orchestrator", "surfaces"}
        for cycle in cycles[:10]:
            if any(c.split(".")[0] in first_party for c in cycle):
                self.findings.append(AuditFinding(
                    category="circular_import",
                    severity="medium",
                    file=cycle[0] if cycle else "",
                    line=0,
                    description=f"Circular import: {' -> '.join(cycle)}",
                    recommendation="Break the cycle by extracting shared code into a lower layer.",
                ))

    # --- dead code ------------------------------------------------------

    def _audit_dead_code(self) -> None:
        """Detect unused private functions and unreachable code."""
        for py in self._python_files():
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            text = py.read_text(encoding="utf-8", errors="ignore")
            private_funcs: list[tuple[str, int]] = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("_") and not node.name.startswith("__"):
                        private_funcs.append((node.name, node.lineno))
            for name, line in private_funcs:
                # Check if the function is called anywhere in the file or its tests
                if name not in text.replace(f"def {name}", ""):
                    # Could be used via reflection — only flag as low-severity
                    self.findings.append(AuditFinding(
                        category="dead_code_candidate",
                        severity="low",
                        file=str(py.relative_to(self.root)),
                        line=line,
                        description=f"Private function '{name}' may be unused",
                        recommendation="Verify usage and remove if dead.",
                    ))

    # --- duplicate logic ------------------------------------------------

    def _audit_duplicate_logic(self) -> None:
        """Detect duplicated function bodies via normalized hash."""
        # Group functions by normalized source length buckets
        buckets: dict[int, list[tuple[str, int, str]]] = defaultdict(list)
        for py in self._python_files():
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = ast.dump(node)
                    # Normalize by stripping variable names
                    normalized = re.sub(r"'[^']+'", "'X'", body)
                    normalized = re.sub(r"[a-z_]+", "id", normalized)
                    length = len(normalized)
                    if length > 200:  # only consider substantial functions
                        buckets[length].append((
                            f"{py.relative_to(self.root)}::{node.name}",
                            node.lineno,
                            normalized,
                        ))
        for length, group in buckets.items():
            if len(group) < 2:
                continue
            # Check for actual duplicates within the bucket
            seen: dict[str, list[tuple[str, int]]] = defaultdict(list)
            for fname, line, norm in group:
                seen[norm].append((fname, line))
            for norm, occurrences in seen.items():
                if len(occurrences) >= 2:
                    self.findings.append(AuditFinding(
                        category="duplicate_logic",
                        severity="medium",
                        file=occurrences[0][0].split("::")[0],
                        line=occurrences[0][1],
                        description=(
                            f"Duplicated function body across {len(occurrences)} locations: "
                            + ", ".join(f for f, _ in occurrences[:5])
                        ),
                        recommendation="Extract the shared logic into a common helper.",
                    ))

    # --- unused APIs ----------------------------------------------------

    def _audit_unused_apis(self) -> None:
        """Detect public API functions/classes never imported elsewhere."""
        all_text: str = ""
        for py in self._python_files():
            try:
                all_text += py.read_text(encoding="utf-8", errors="ignore") + "\n"
            except OSError:
                continue
        for py in self._python_files():
            if "tests" in py.parts:
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = node.name
                    if name.startswith("_"):
                        continue
                    # Count occurrences excluding the definition
                    occurrences = len(re.findall(rf"\b{re.escape(name)}\b", all_text))
                    if occurrences <= 1:
                        self.findings.append(AuditFinding(
                            category="unused_api_candidate",
                            severity="low",
                            file=str(py.relative_to(self.root)),
                            line=node.lineno,
                            description=f"Public API '{name}' is never imported or called elsewhere",
                            recommendation="Remove if truly unused, or document as part of the public contract.",
                        ))

    # --- unreachable code ----------------------------------------------

    def _audit_unreachable_code(self) -> None:
        """Detect code after return/raise/break/continue."""
        for py in self._python_files():
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for stmt in ast.walk(node):
                    if not isinstance(stmt, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                        continue
                    body = getattr(stmt, "body", []) or []
                    for i, child in enumerate(body[:-1]):
                        if isinstance(child, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                            self.findings.append(AuditFinding(
                                category="unreachable_code",
                                severity="low",
                                file=str(py.relative_to(self.root)),
                                line=getattr(body[i + 1], "lineno", 0),
                                description=f"Unreachable code after {type(child).__name__}",
                                recommendation="Remove the unreachable statements.",
                            ))

    # --- deprecated interfaces -----------------------------------------

    def _audit_deprecated_interfaces(self) -> None:
        """Detect deprecated markers."""
        for py in self._python_files():
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if "deprecated" in line.lower() and not line.strip().startswith("#"):
                    self.findings.append(AuditFinding(
                        category="deprecated_interface",
                        severity="info",
                        file=str(py.relative_to(self.root)),
                        line=i,
                        description=f"Deprecated marker: {line.strip()[:100]}",
                        recommendation="Plan removal in the next major version.",
                    ))

    # --- security issues ------------------------------------------------

    def _audit_security_issues(self) -> None:
        """Quick static security scan (bandit covers the rest)."""
        dangerous_patterns = [
            (r"\beval\s*\(", "eval() usage"),
            (r"\bexec\s*\(", "exec() usage"),
            (r"\b__import__\s*\(", "__import__() usage"),
            (r"\bshell\s*=\s*True", "shell=True in subprocess"),
            (r"\bpickle\.loads?\s*\(", "pickle deserialization"),
            (r"\byaml\.load\s*\(", "unsafe yaml.load (use safe_load)"),
        ]
        for py in self._python_files():
            if "tests" in py.parts:
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern, desc in dangerous_patterns:
                for m in re.finditer(pattern, text):
                    line_num = text[:m.start()].count("\n") + 1
                    self.findings.append(AuditFinding(
                        category="security_issue",
                        severity="high",
                        file=str(py.relative_to(self.root)),
                        line=line_num,
                        description=desc,
                        recommendation="Replace with a safer alternative.",
                    ))

    # --- performance bottlenecks ---------------------------------------

    def _audit_performance_bottlenecks(self) -> None:
        """Detect common Python performance anti-patterns."""
        for py in self._python_files():
            if "tests" in py.parts:
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # Blocking calls in async functions
            for m in re.finditer(
                r"async\s+def\s+\w+[^:]*:\s*(?:#[^\n]*\n|\s*\n|\s*[^a-zA-Z\n])*?\s*(?:time\.sleep|requests\.get|requests\.post|urllib\.request\.urlopen)\s*\(",
                text, re.DOTALL,
            ):
                line_num = text[:m.start()].count("\n") + 1
                self.findings.append(AuditFinding(
                    category="performance_bottleneck",
                    severity="medium",
                    file=str(py.relative_to(self.root)),
                    line=line_num,
                    description="Blocking call inside async function",
                    recommendation="Use asyncio.to_thread() or an async-native alternative.",
                ))
            # List append in tight loops (heuristic)
            for m in re.finditer(r"for\s+\w+\s+in\s+\w+:\s*\n\s*\w+\.append\(", text):
                line_num = text[:m.start()].count("\n") + 1
                self.findings.append(AuditFinding(
                    category="performance_bottleneck",
                    severity="low",
                    file=str(py.relative_to(self.root)),
                    line=line_num,
                    description="List append in for-loop — consider list comprehension",
                    recommendation="Replace with a list comprehension for better performance.",
                ))

    # --- helpers --------------------------------------------------------

    def _python_files(self) -> list[Path]:
        out: list[Path] = []
        for p in self.root.rglob("*.py"):
            if any(seg in p.parts for seg in self.SKIP_DIRS):
                continue
            out.append(p)
        return out

    def _build_report(self) -> AuditReport:
        by_category: dict[str, int] = defaultdict(int)
        by_severity: dict[str, int] = defaultdict(int)
        for f in self.findings:
            by_category[f.category] += 1
            by_severity[f.severity] += 1
        critical = by_severity.get("critical", 0)
        high = by_severity.get("high", 0)
        medium = by_severity.get("medium", 0)
        low = by_severity.get("low", 0)
        info = by_severity.get("info", 0)
        if critical > 0:
            status = "FAIL"
            summary = f"Audit FAILED: {critical} critical, {high} high, {medium} medium, {low} low, {info} info"
        elif high > 0:
            status = "WARNING"
            summary = f"Audit WARNING: {high} high, {medium} medium, {low} low, {info} info"
        else:
            status = "PASS"
            summary = f"Audit PASSED: {medium} medium, {low} low, {info} info"
        return AuditReport(
            generated_at=datetime.now(UTC).isoformat(),
            root=str(self.root),
            findings=[{**asdict(f)} for f in self.findings],
            stats={
                "total_findings": len(self.findings),
                "by_category": dict(by_category),
                "by_severity": dict(by_severity),
                "status": status,
            },
            summary=summary,
        )


# ---------------------------------------------------------------------------
# Technical Debt Scanner
# ---------------------------------------------------------------------------


class TechnicalDebtScanner:
    """Scan for TODOs, FIXMEs, placeholders, suppressions, skipped tests."""

    PATTERNS: tuple[tuple[str, str], ...] = (
        (r"\bTODO\b", "todo"),
        (r"\bFIXME\b", "fixme"),
        (r"\bXXX\b", "xxx"),
        (r"\bHACK\b", "hack"),
        (r"\bPLACEHOLDER\b", "placeholder"),
        (r"\bMOCK\b.*production", "mock_in_production"),
        (r"#\s*type:\s*ignore", "type_ignore_suppression"),
        (r"#\s*noqa", "noqa_suppression"),
        (r"#\s*nosec", "nosec_suppression"),
        (r"@pytest\.mark\.skip", "skipped_test"),
        (r"pytest\.skip\s*\(", "skipped_test"),
        (r"@unittest\.skip", "skipped_test"),
        (r"@pytest\.fixture\s*\(\s*autouse.*\)\s*\n\s*def\s+skip", "conditionally_skipped"),
        (r"^\s*#\s*[a-zA-Z_]+\s*=\s*", "commented_code_candidate"),
    )

    SKIP_DIRS: frozenset[str] = frozenset({
        ".venv", "node_modules", ".git", "__pycache__",
        "build", "dist", ".next", ".mypy_cache", ".ruff_cache",
        "coverage", "site",
    })

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.findings: list[AuditFinding] = []

    def scan(self) -> AuditReport:
        for py in self._python_files():
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for pattern, category in self.PATTERNS:
                    if re.search(pattern, line):
                        # Skip legitimate noqa with specific code
                        if category == "noqa_suppression" and re.search(r"#\s*noqa:\s*[A-Z]+", line):
                            continue
                        # Skip noqa: S603,S607 etc. (specific) - allowed
                        self.findings.append(AuditFinding(
                            category=category,
                            severity=self._severity(category),
                            file=str(py.relative_to(self.root)),
                            line=i,
                            description=line.strip()[:200],
                            recommendation=self._recommendation(category),
                        ))
        return self._build_report()

    def _severity(self, category: str) -> str:
        if category in ("fixme", "mock_in_production"):
            return "high"
        if category in ("todo", "placeholder", "skipped_test"):
            return "medium"
        if category in ("type_ignore_suppression", "noqa_suppression", "nosec_suppression"):
            return "low"
        return "info"

    def _recommendation(self, category: str) -> str:
        recs = {
            "todo": "Resolve before LTS freeze.",
            "fixme": "Must be fixed before LTS certification.",
            "placeholder": "Replace with real implementation.",
            "mock_in_production": "Replace with real implementation.",
            "skipped_test": "Re-enable or remove the test.",
            "type_ignore_suppression": "Fix the type issue and remove the suppression.",
            "noqa_suppression": "Fix the lint issue and remove the suppression.",
            "nosec_suppression": "Fix the security issue and remove the suppression.",
            "commented_code_candidate": "Remove commented-out code.",
        }
        return recs.get(category, "Review and address.")

    def _python_files(self) -> list[Path]:
        out: list[Path] = []
        for p in self.root.rglob("*.py"):
            if any(seg in p.parts for seg in self.SKIP_DIRS):
                continue
            out.append(p)
        return out

    def _build_report(self) -> AuditReport:
        by_category: dict[str, int] = defaultdict(int)
        by_severity: dict[str, int] = defaultdict(int)
        for f in self.findings:
            by_category[f.category] += 1
            by_severity[f.severity] += 1
        return AuditReport(
            generated_at=datetime.now(UTC).isoformat(),
            root=str(self.root),
            findings=[{**asdict(f)} for f in self.findings],
            stats={
                "total_findings": len(self.findings),
                "by_category": dict(by_category),
                "by_severity": dict(by_severity),
            },
            summary=(
                f"Technical debt scan: {len(self.findings)} findings "
                f"({by_severity.get('high', 0)} high, {by_severity.get('medium', 0)} medium, "
                f"{by_severity.get('low', 0)} low, {by_severity.get('info', 0)} info)"
            ),
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="AAiOS LTS Repository Audit")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--out-dir", default="lts-audit", help="Output directory for reports")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Auditing repository at {root}...")
    auditor = RepositoryAuditor(root)
    audit_report = auditor.audit()
    print(f"  Audit: {audit_report.summary}")

    print("Scanning for technical debt...")
    debt_scanner = TechnicalDebtScanner(root)
    debt_report = debt_scanner.scan()
    print(f"  Debt: {debt_report.summary}")

    # Write reports
    (out_dir / "repository_audit_report.json").write_text(
        json.dumps(audit_report.to_dict(), indent=2, default=str)
    )
    (out_dir / "technical_debt_report.json").write_text(
        json.dumps(debt_report.to_dict(), indent=2, default=str)
    )

    # Architecture compliance + dependency graph
    arch_report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "layers": [
            {"name": name, "description": desc, "order": i}
            for i, (name, desc) in enumerate(RepositoryAuditor.LAYERS)
        ],
        "invariant_violations": [
            f for f in audit_report.findings
            if f["category"] in ("INV-02_violation", "INV-09_violation", "layer_violation")
        ],
        "dependency_graph": {
            k: sorted(v) for k, v in auditor._dep_graph.items()
            if k and any(k.startswith(p) for p in
                         ("core", "services", "agents", "supervisor", "orchestrator", "surfaces"))
        },
    }
    (out_dir / "architecture_compliance_report.json").write_text(
        json.dumps(arch_report, indent=2, default=str)
    )

    print(f"\nReports written to {out_dir}/")
    print(f"  - repository_audit_report.json ({len(audit_report.findings)} findings)")
    print(f"  - technical_debt_report.json ({len(debt_report.findings)} findings)")
    print("  - architecture_compliance_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
