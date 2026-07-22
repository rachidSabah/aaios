"""Phase 19 — Documentation Intelligence.

Continuously analyzes README, architecture docs, developer guides, API docs,
CLI docs, SDK docs, migration guides, release notes, and user manuals.
Detects outdated / missing / broken / unused docs and missing examples.
Generates documentation recommendations, completeness score, consistency
score, and documentation coverage.

READ-ONLY — never writes files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "DocAnalysisReport",
    "DocIssue",
    "DocPageInfo",
    "DocType",
    "DocumentationIntelligenceEngine",
]


class DocType(StrEnum):
    README = "readme"
    ARCHITECTURE = "architecture"
    DEVELOPER_GUIDE = "developer_guide"
    API_DOC = "api_doc"
    CLI_DOC = "cli_doc"
    SDK_DOC = "sdk_doc"
    MIGRATION_GUIDE = "migration_guide"
    RELEASE_NOTES = "release_notes"
    USER_MANUAL = "user_manual"
    UNKNOWN = "unknown"


@dataclass
class DocPageInfo:
    """Information about a single documentation page."""

    page_id: str = field(default_factory=lambda: uuid4().hex[:8])
    path: str = ""
    doc_type: str = DocType.UNKNOWN.value
    title: str = ""
    line_count: int = 0
    word_count: int = 0
    code_blocks: int = 0
    links: list[str] = field(default_factory=list)
    broken_links: list[str] = field(default_factory=list)
    has_examples: bool = False
    last_modified: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "path": self.path,
            "doc_type": self.doc_type,
            "title": self.title,
            "line_count": self.line_count,
            "word_count": self.word_count,
            "code_blocks": self.code_blocks,
            "links": list(self.links),
            "broken_links": list(self.broken_links),
            "has_examples": self.has_examples,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
        }


@dataclass
class DocIssue:
    """A documentation issue detected by the engine."""

    issue_id: str = field(default_factory=lambda: uuid4().hex[:8])
    issue_type: str = ""  # outdated | missing | broken_ref | unused | missing_examples
    severity: str = "medium"
    page: str = ""
    description: str = ""
    recommendation: str = ""
    confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "page": self.page,
            "description": self.description,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class DocAnalysisReport:
    """A complete documentation intelligence report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    pages: list[DocPageInfo] = field(default_factory=list)
    issues: list[DocIssue] = field(default_factory=list)
    completeness_score: float = 0.0  # 0..1
    consistency_score: float = 0.0  # 0..1
    coverage_pct: float = 0.0  # % of source modules with corresponding docs
    recommendations: list[str] = field(default_factory=list)
    by_type: dict[str, int] = field(default_factory=dict)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "pages": [p.to_dict() for p in self.pages],
            "issues": [i.to_dict() for i in self.issues],
            "completeness_score": round(self.completeness_score, 4),
            "consistency_score": round(self.consistency_score, 4),
            "coverage_pct": round(self.coverage_pct, 2),
            "recommendations": list(self.recommendations),
            "by_type": dict(self.by_type),
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class DocumentationIntelligenceEngine:
    """Phase 19 — Documentation Intelligence."""

    # Expected top-level docs for a healthy project
    EXPECTED_TOP_LEVEL: tuple[str, ...] = (
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "docs/ARCHITECTURE.md",
        "docs/DEVELOPER.md",
        "docs/API.md",
        "docs/CLI.md",
        "docs/MIGRATION.md",
        "docs/SECURITY.md",
    )

    # --- public API -----------------------------------------------------

    async def analyze(self, root: str | Path) -> DocAnalysisReport:
        """Analyze the documentation of the project at ``root``."""
        root_path = Path(root)
        report = DocAnalysisReport()
        if not root_path.exists():
            return report

        # Discover pages
        pages = self._discover_pages(root_path)
        report.pages = pages
        for p in pages:
            report.by_type[p.doc_type] = report.by_type.get(p.doc_type, 0) + 1

        # Issues: missing top-level docs
        for expected in self.EXPECTED_TOP_LEVEL:
            if not (root_path / expected).exists():
                report.issues.append(
                    DocIssue(
                        issue_type="missing",
                        severity="high" if expected in ("README.md", "LICENSE") else "medium",
                        page=expected,
                        description=f"Expected top-level document {expected} not found.",
                        recommendation=f"Create {expected} following project conventions.",
                        confidence=0.95,
                    )
                )

        # Issues: per-page analysis
        for page in pages:
            self._analyze_page(page, root_path, report)

        # Coverage: % of source modules with corresponding docs
        report.coverage_pct = self._compute_coverage(root_path, pages)
        # Completeness: weighted score
        report.completeness_score = self._compute_completeness(report)
        # Consistency: how well docs reference each other consistently
        report.consistency_score = self._compute_consistency(report)
        report.recommendations = self._build_recommendations(report)
        return report

    async def recommendations(self, root: str | Path) -> list[dict[str, Any]]:
        """Return only recommendations (quick-call form)."""
        report = await self.analyze(root)
        return [
            {"text": r, "confidence": 0.7, "requires_approval": True}
            for r in report.recommendations
        ]

    # --- helpers --------------------------------------------------------

    def _discover_pages(self, root: Path) -> list[DocPageInfo]:
        pages: list[DocPageInfo] = []
        candidates: list[Path] = []
        # Markdown anywhere
        candidates.extend(root.rglob("*.md"))
        # Restructured text
        candidates.extend(root.rglob("*.rst"))
        # Skip common noise
        for p in candidates:
            if any(
                seg in p.parts
                for seg in ("node_modules", ".venv", ".git", "__pycache__", "build", "dist", "site")
            ):
                continue
            if p.name in ("CHANGELOG.md",) and p.parent != root:
                continue
            pages.append(self._build_page_info(p, root))
        return pages

    def _build_page_info(self, p: Path, root: Path) -> DocPageInfo:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        lines = text.splitlines()
        # Title = first H1
        title = ""
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if not title:
            title = p.stem.replace("_", " ").replace("-", " ").title()
        # Code blocks (```...```)
        code_blocks = len(re.findall(r"^```", text, re.M)) // 2
        # Links [text](target)
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        # Filter to local links (no http)
        local_links = [
            link for link in links if not link.startswith(("http://", "https://", "mailto:", "#"))
        ]
        # Broken links: local targets that do not exist
        broken: list[str] = []
        for link in local_links:
            target = (p.parent / link).resolve()
            if not target.exists():
                broken.append(link)
        has_examples = code_blocks > 0
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        except OSError:
            mtime = None
        return DocPageInfo(
            path=str(p.relative_to(root)),
            doc_type=self._classify_doc(p, root).value,
            title=title,
            line_count=len(lines),
            word_count=len(text.split()),
            code_blocks=code_blocks,
            links=local_links,
            broken_links=broken,
            has_examples=has_examples,
            last_modified=mtime,
        )

    def _classify_doc(self, p: Path, root: Path) -> DocType:
        rel = str(p.relative_to(root)).lower()
        name = p.name.lower()
        if name == "readme.md":
            return DocType.README
        if "migration" in name or "migrat" in rel:
            return DocType.MIGRATION_GUIDE
        if "release" in name or "changelog" in name:
            return DocType.RELEASE_NOTES
        if "api" in name or "api" in rel:
            return DocType.API_DOC
        if "cli" in name or "cli" in rel:
            return DocType.CLI_DOC
        if "sdk" in name or "sdk" in rel:
            return DocType.SDK_DOC
        if "architecture" in name or "architecture" in rel:
            return DocType.ARCHITECTURE
        if "developer" in name or "develop" in rel:
            return DocType.DEVELOPER_GUIDE
        if "user" in name or "manual" in name or "guide" in name:
            return DocType.USER_MANUAL
        return DocType.UNKNOWN

    def _analyze_page(self, page: DocPageInfo, root: Path, report: DocAnalysisReport) -> None:
        # Broken links
        for bl in page.broken_links:
            report.issues.append(
                DocIssue(
                    issue_type="broken_ref",
                    severity="medium",
                    page=page.path,
                    description=f"Broken link: {bl}",
                    recommendation=f"Fix or remove the broken reference in {page.path}.",
                    confidence=0.9,
                )
            )
        # Missing examples (no code blocks but the doc is technical)
        if not page.has_examples and page.doc_type in (
            DocType.API_DOC.value,
            DocType.CLI_DOC.value,
            DocType.SDK_DOC.value,
            DocType.DEVELOPER_GUIDE.value,
        ):
            report.issues.append(
                DocIssue(
                    issue_type="missing_examples",
                    severity="medium",
                    page=page.path,
                    description="Technical document has no code examples.",
                    recommendation="Add runnable code examples for each documented feature.",
                    confidence=0.7,
                )
            )
        # Outdated: not modified in 180 days
        if page.last_modified:
            age_days = (datetime.now(UTC) - page.last_modified).days
            if age_days > 180 and page.doc_type in (
                DocType.API_DOC.value,
                DocType.MIGRATION_GUIDE.value,
                DocType.RELEASE_NOTES.value,
            ):
                report.issues.append(
                    DocIssue(
                        issue_type="outdated",
                        severity="medium",
                        page=page.path,
                        description=f"Document not updated in {age_days} days.",
                        recommendation="Review and refresh this document.",
                        confidence=0.7,
                    )
                )
        # Thin doc
        if page.word_count < 50 and page.doc_type != DocType.UNKNOWN.value:
            report.issues.append(
                DocIssue(
                    issue_type="missing",
                    severity="low",
                    page=page.path,
                    description=f"Document has only {page.word_count} words.",
                    recommendation="Expand the document with substantive content.",
                    confidence=0.8,
                )
            )

    def _compute_coverage(self, root: Path, pages: list[DocPageInfo]) -> float:
        """% of source modules with a corresponding doc page."""
        source_files: list[Path] = []
        for p in root.rglob("*.py"):
            if any(
                seg in p.parts
                for seg in (
                    ".venv",
                    "node_modules",
                    ".git",
                    "__pycache__",
                    "build",
                    "dist",
                    "tests",
                )
            ):
                continue
            source_files.append(p)
        if not source_files:
            return 0.0
        doc_names = {Path(p.path).stem.lower() for p in pages}
        covered = 0
        for sf in source_files:
            stem = sf.stem.lower()
            if stem in doc_names or f"{stem}_doc" in doc_names or f"{stem}_guide" in doc_names:
                covered += 1
        return round(covered / len(source_files) * 100, 2)

    def _compute_completeness(self, report: DocAnalysisReport) -> float:
        expected = set(self.EXPECTED_TOP_LEVEL)
        found = {p.path for p in report.pages}
        # Normalize found to top-level relative paths
        found_top = {f for f in found if "/" not in f} | {f for f in found if f.startswith("docs/")}
        missing = expected - found_top
        if not expected:
            return 1.0
        return round(1.0 - len(missing) / len(expected), 4)

    def _compute_consistency(self, report: DocAnalysisReport) -> float:
        """How consistent are docs? Penalize broken refs and missing examples."""
        if not report.pages:
            return 0.0
        penalty = 0.0
        for issue in report.issues:
            if issue.issue_type == "broken_ref":
                penalty += 0.05
            elif issue.issue_type == "missing_examples":
                penalty += 0.03
            elif issue.issue_type == "outdated":
                penalty += 0.02
        return round(max(0.0, 1.0 - penalty), 4)

    def _build_recommendations(self, report: DocAnalysisReport) -> list[str]:
        recs: list[str] = []
        missing_types = {
            DocType.ARCHITECTURE.value,
            DocType.API_DOC.value,
            DocType.CLI_DOC.value,
            DocType.MIGRATION_GUIDE.value,
        }
        present_types = {p.doc_type for p in report.pages}
        for mt in missing_types:
            if mt not in present_types:
                recs.append(f"Add {mt} documentation — currently missing.")
        if any(i.issue_type == "broken_ref" for i in report.issues):
            recs.append("Fix broken cross-references throughout the documentation.")
        if any(i.issue_type == "missing_examples" for i in report.issues):
            recs.append("Add runnable examples to technical docs.")
        if report.coverage_pct < 50.0:
            recs.append("Increase documentation coverage — currently below 50%.")
        if report.consistency_score < 0.7:
            recs.append(
                "Improve documentation consistency — fix broken refs and outdated sections."
            )
        if not recs:
            recs.append("Documentation posture is healthy — continue regular reviews.")
        return recs
