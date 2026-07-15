"""Repository Intelligence + Document Intelligence + Quality Assurance.

Phases 18-19-21: Repository analysis, document understanding, quality validation.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger
from services.knowledge.models import KnowledgeEntry

_log = get_logger(__name__)

__all__ = [
    "DocIntelligenceResult",
    "DocumentIntelligence",
    "QualityAssurance",
    "QualityIssue",
    "RepoAnalysis",
    "RepoIssue",
    "RepositoryIntelligenceEngine",
]


@dataclass
class RepoIssue:
    """An issue found by repository intelligence."""

    issue_id: str = ""
    issue_type: str = ""  # dead_code, unused_api, circular_dep, arch_drift, duplication, missing_doc, broken_ref, dep_risk, security_risk
    severity: str = "medium"
    file: str = ""
    line: int = 0
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "description": self.description,
            "recommendation": self.recommendation,
        }


@dataclass
class RepoAnalysis:
    """Repository analysis result."""

    total_files: int = 0
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_tests: int = 0
    issues: list[RepoIssue] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    health_score: float = 0.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_classes": self.total_classes,
            "total_functions": self.total_functions,
            "total_tests": self.total_tests,
            "issues": [i.to_dict() for i in self.issues],
            "dependencies": list(self.dependencies),
            "health_score": round(self.health_score, 2),
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class QualityIssue:
    """A knowledge quality issue."""

    issue_type: str = ""  # accuracy, completeness, freshness, consistency, broken_link, missing_metadata, duplicate
    severity: str = "medium"
    entry_id: str = ""
    description: str = ""
    repair_suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "entry_id": self.entry_id,
            "description": self.description,
            "repair_suggestion": self.repair_suggestion,
        }


@dataclass
class DocIntelligenceResult:
    """Document intelligence extraction result."""

    file_path: str = ""
    file_type: str = ""
    entities: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    relationships: list[dict[str, str]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "entities": list(self.entities),
            "concepts": list(self.concepts),
            "relationships": list(self.relationships),
            "tables": list(self.tables),
            "references": list(self.references),
            "metadata": dict(self.metadata),
            "summary": self.summary[:500],
        }


class RepositoryIntelligenceEngine:
    """Continuously analyzes the repository for architecture issues.

    Phase 18: Enterprise Repository Intelligence.
    """

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    async def analyze(self) -> RepoAnalysis:
        """Analyze the repository."""
        analysis = RepoAnalysis()
        py_files: list[Path] = []
        for src_dir in [self._root / "services", self._root / "core", self._root / "agents",
                        self._root / "supervisor", self._root / "orchestrator", self._root / "surfaces"]:
            if src_dir.exists():
                py_files.extend(src_dir.rglob("*.py"))
        test_files = list((self._root / "tests").rglob("*.py")) if (self._root / "tests").exists() else []
        analysis.total_files = len(py_files)
        analysis.total_tests = len(test_files)
        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                analysis.total_lines += len(source.splitlines())
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        analysis.total_classes += 1
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        analysis.total_functions += 1
                        # Check for unused private functions
                        if node.name.startswith("_") and not node.name.startswith("__"):
                            if not self._is_called(node.name, py_file):
                                analysis.issues.append(RepoIssue(
                                    issue_type="dead_code",
                                    severity="low",
                                    file=str(py_file.relative_to(self._root)),
                                    line=node.lineno,
                                    description=f"Private function '{node.name}' may be unused",
                                    recommendation="Remove if truly unused",
                                ))
            except Exception:
                pass
        # Check for missing docs
        for py_file in py_files[:20]:  # limit
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and not ast.get_docstring(node):
                        analysis.issues.append(RepoIssue(
                            issue_type="missing_doc",
                            severity="low",
                            file=str(py_file.relative_to(self._root)),
                            line=node.lineno,
                            description=f"Class '{node.name}' has no docstring",
                            recommendation="Add a docstring",
                        ))
            except Exception:
                pass
        # Check for missing test files
        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue
            test_name = f"test_{py_file.stem}.py"
            if not (self._root / "tests" / "unit" / test_name).exists():
                analysis.issues.append(RepoIssue(
                    issue_type="missing_test",
                    severity="medium",
                    file=str(py_file.relative_to(self._root)),
                    description=f"No test file for {py_file.name}",
                    recommendation=f"Create {test_name}",
                ))
        # Health score
        score = 100.0
        score -= len([i for i in analysis.issues if i.severity == "critical"]) * 10
        score -= len([i for i in analysis.issues if i.severity == "high"]) * 5
        score -= len([i for i in analysis.issues if i.severity == "medium"]) * 2
        score -= len([i for i in analysis.issues if i.severity == "low"]) * 0.5
        analysis.health_score = max(0, score)
        analysis.issues = analysis.issues[:50]  # limit
        return analysis

    def _is_called(self, func_name: str, current_file: Path) -> bool:
        for py_file in self._root.rglob("*.py"):
            if ".venv" in str(py_file) or "node_modules" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                if func_name + "(" in source:
                    return True
            except Exception:
                pass
        return False


class DocumentIntelligence:
    """Intelligent document understanding for multiple formats.

    Phase 19: Enterprise Document Intelligence.
    """

    async def analyze(self, file_path: str, content: str = "") -> DocIntelligenceResult:
        """Analyze a document and extract knowledge."""
        path = Path(file_path)
        file_type = path.suffix.lstrip(".") or "txt"
        result = DocIntelligenceResult(file_path=file_path, file_type=file_type)
        if not content:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
        if not content:
            return result
        # Extract based on file type
        if file_type in ("py", "python"):
            await self._analyze_python(content, result)
        elif file_type in ("md", "markdown"):
            await self._analyze_markdown(content, result)
        elif file_type in ("json", "yaml", "yml", "xml"):
            await self._analyze_structured(content, result)
        elif file_type in ("csv",):
            await self._analyze_csv(content, result)
        else:
            await self._analyze_text(content, result)
        return result

    async def _analyze_python(self, content: str, result: DocIntelligenceResult) -> None:
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result.entities.append(node.name)
            result.summary = f"Python file with {len(result.entities)} classes/functions"
        except Exception:
            result.summary = "Python file (parse error)"

    async def _analyze_markdown(self, content: str, result: DocIntelligenceResult) -> None:
        headers = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)
        result.entities = headers
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        result.references = [url for _, url in links]
        result.summary = f"Markdown with {len(headers)} sections, {len(links)} links"

    async def _analyze_structured(self, content: str, result: DocIntelligenceResult) -> None:
        import json
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                result.entities = list(data.keys())
                result.summary = f"JSON/YAML with {len(result.entities)} keys"
            elif isinstance(data, list):
                result.summary = f"JSON array with {len(data)} items"
        except Exception:
            result.summary = "Structured file"

    async def _analyze_csv(self, content: str, result: DocIntelligenceResult) -> None:
        lines = content.strip().split("\n")
        if lines:
            result.entities = lines[0].split(",")
            result.tables.append({"rows": len(lines) - 1, "columns": len(result.entities)})
            result.summary = f"CSV with {len(lines)-1} rows, {len(result.entities)} columns"

    async def _analyze_text(self, content: str, result: DocIntelligenceResult) -> None:
        words = re.findall(r"\b[A-Z][a-z]+\b", content)
        result.entities = list(set(words))[:20]
        result.summary = f"Text file ({len(content)} chars, {len(content.splitlines())} lines)"


class QualityAssurance:
    """Continuous knowledge quality validation.

    Phase 21: Knowledge Quality Assurance.
    """

    async def validate(self, entries: list[KnowledgeEntry]) -> list[QualityIssue]:
        """Validate knowledge entries and return issues."""
        issues: list[QualityIssue] = []
        for entry in entries:
            # Completeness
            if not entry.summary:
                issues.append(QualityIssue(
                    issue_type="completeness",
                    severity="low",
                    entry_id=entry.entry_id,
                    description="Missing summary",
                    repair_suggestion="Add a concise summary",
                ))
            if not entry.labels:
                issues.append(QualityIssue(
                    issue_type="completeness",
                    severity="low",
                    entry_id=entry.entry_id,
                    description="Missing labels",
                    repair_suggestion="Add relevant labels for discoverability",
                ))
            # Freshness
            if entry.updated_at:
                age = (datetime.now(UTC) - entry.updated_at).total_seconds() / 86400
                if age > 180:
                    issues.append(QualityIssue(
                        issue_type="freshness",
                        severity="medium",
                        entry_id=entry.entry_id,
                        description=f"Entry is {age:.0f} days old",
                        repair_suggestion="Review and update if needed",
                    ))
            # Confidence
            if entry.source_confidence < 0.3:
                issues.append(QualityIssue(
                    issue_type="accuracy",
                    severity="medium",
                    entry_id=entry.entry_id,
                    description=f"Low source confidence: {entry.source_confidence:.2f}",
                    repair_suggestion="Verify the source and increase confidence",
                ))
        # Check for duplicates
        seen_hashes: dict[str, str] = {}
        for entry in entries:
            content_hash = __import__("hashlib").sha256(entry.content[:500].encode()).hexdigest()[:16]
            if content_hash in seen_hashes:
                issues.append(QualityIssue(
                    issue_type="duplicate",
                    severity="medium",
                    entry_id=entry.entry_id,
                    description=f"Duplicate of entry {seen_hashes[content_hash]}",
                    repair_suggestion="Merge duplicates",
                ))
            else:
                seen_hashes[content_hash] = entry.entry_id
        return issues

    async def repair_suggestions(self, issues: list[QualityIssue]) -> list[dict[str, Any]]:
        """Generate repair suggestions for quality issues."""
        suggestions: list[dict[str, Any]] = []
        for issue in issues:
            suggestions.append({
                "issue_type": issue.issue_type,
                "entry_id": issue.entry_id,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.repair_suggestion,
            })
        return suggestions
