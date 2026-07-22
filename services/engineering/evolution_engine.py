"""Phase 20 — Repository Evolution Engine.

Tracks repository evolution: commits, branches, releases, tags, architectural
changes, technical debt trends, performance trends, bug trends, feature growth.
Generates timeline, evolution dashboard, growth analytics, and historical
comparisons.

Uses git metadata via the GitGateway (core/gateway/git.py) — never modifies
the repository. All git I/O is centralized in the gateway to satisfy INV-02.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.gateway.git import GitGateway
from core.logging import get_logger

_log = get_logger(__name__)

__all__ = [
    "CommitInfo",
    "EvolutionDashboard",
    "EvolutionReport",
    "ReleaseInfo",
    "RepositoryEvolutionEngine",
    "TimelineEntry",
]


@dataclass
class CommitInfo:
    """Information about a single commit."""

    commit_id: str = ""
    short_hash: str = ""
    author: str = ""
    author_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    message: str = ""
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    is_merge: bool = False
    is_breaking: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_id": self.commit_id,
            "short_hash": self.short_hash,
            "author": self.author,
            "author_date": self.author_date.isoformat(),
            "message": self.message,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "is_merge": self.is_merge,
            "is_breaking": self.is_breaking,
        }


@dataclass
class ReleaseInfo:
    """Information about a release (git tag)."""

    tag: str = ""
    name: str = ""
    date: datetime = field(default_factory=lambda: datetime.now(UTC))
    commit: str = ""
    is_prerelease: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "name": self.name,
            "date": self.date.isoformat(),
            "commit": self.commit,
            "is_prerelease": self.is_prerelease,
        }


@dataclass
class TimelineEntry:
    """A single entry in the repository timeline."""

    entry_id: str = field(default_factory=lambda: uuid4().hex[:8])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    kind: str = "commit"  # commit | release | tag | branch | merge | breaking
    title: str = ""
    description: str = ""
    actor: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "actor": self.actor,
        }


@dataclass
class EvolutionDashboard:
    """Dashboard data summarizing repository evolution."""

    total_commits: int = 0
    total_authors: int = 0
    total_branches: int = 0
    total_releases: int = 0
    total_tags: int = 0
    commits_last_7d: int = 0
    commits_last_30d: int = 0
    commits_last_90d: int = 0
    avg_commits_per_week: float = 0.0
    active_branches: list[str] = field(default_factory=list)
    top_authors: list[dict[str, Any]] = field(default_factory=list)
    by_month: list[dict[str, Any]] = field(default_factory=list)
    technical_debt_trend: list[dict[str, Any]] = field(default_factory=list)
    bug_trend: list[dict[str, Any]] = field(default_factory=list)
    feature_growth: list[dict[str, Any]] = field(default_factory=list)
    performance_trend: list[dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_commits": self.total_commits,
            "total_authors": self.total_authors,
            "total_branches": self.total_branches,
            "total_releases": self.total_releases,
            "total_tags": self.total_tags,
            "commits_last_7d": self.commits_last_7d,
            "commits_last_30d": self.commits_last_30d,
            "commits_last_90d": self.commits_last_90d,
            "avg_commits_per_week": round(self.avg_commits_per_week, 2),
            "active_branches": list(self.active_branches),
            "top_authors": list(self.top_authors),
            "by_month": list(self.by_month),
            "technical_debt_trend": list(self.technical_debt_trend),
            "bug_trend": list(self.bug_trend),
            "feature_growth": list(self.feature_growth),
            "performance_trend": list(self.performance_trend),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class EvolutionReport:
    """A complete repository evolution report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    repository: str = ""
    timeline: list[TimelineEntry] = field(default_factory=list)
    dashboard: EvolutionDashboard = field(default_factory=EvolutionDashboard)
    historical_comparisons: list[dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "repository": self.repository,
            "timeline": [t.to_dict() for t in self.timeline],
            "dashboard": self.dashboard.to_dict(),
            "historical_comparisons": list(self.historical_comparisons),
            "generated_at": self.generated_at.isoformat(),
        }


class RepositoryEvolutionEngine:
    """Phase 20 — Repository Evolution.

    Uses git via subprocess (read-only). Falls back gracefully when git is
    unavailable or when the path is not a git repository.
    """

    def __init__(self, repo_root: str | Path = ".") -> None:
        self._root = Path(repo_root)
        self._git = GitGateway(repo_root=self._root)

    # --- public API -----------------------------------------------------

    async def timeline(self, limit: int = 100) -> list[TimelineEntry]:
        """Build a unified timeline of commits, releases, and merges."""
        entries: list[TimelineEntry] = []
        commits = await self._collect_commits(limit=limit)
        for c in commits:
            entries.append(
                TimelineEntry(
                    timestamp=c.author_date,
                    kind="breaking" if c.is_breaking else ("merge" if c.is_merge else "commit"),
                    title=c.message.splitlines()[0] if c.message else c.short_hash,
                    description=c.message,
                    actor=c.author,
                )
            )
        releases = await self._collect_releases()
        for r in releases:
            entries.append(
                TimelineEntry(
                    timestamp=r.date,
                    kind="release",
                    title=f"Release {r.tag}",
                    description=r.name or r.tag,
                    actor="release-pipeline",
                )
            )
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    async def dashboard(self) -> EvolutionDashboard:
        """Build an evolution dashboard."""
        dash = EvolutionDashboard()
        commits = await self._collect_commits(limit=2000)
        dash.total_commits = len(commits)
        # Authors
        authors: dict[str, int] = {}
        for c in commits:
            authors[c.author] = authors.get(c.author, 0) + 1
        dash.total_authors = len(authors)
        top_authors_list: list[dict[str, Any]] = [
            {"author": a, "commits": n} for a, n in authors.items()
        ]
        top_authors_list.sort(key=lambda x: x["commits"], reverse=True)
        dash.top_authors = top_authors_list[:10]
        # Branches
        dash.active_branches = await self._collect_branches()
        dash.total_branches = len(dash.active_branches)
        # Releases / tags
        releases = await self._collect_releases()
        dash.total_releases = len(releases)
        dash.total_tags = len(await self._collect_tags())
        # Recent commit counts
        now = datetime.now(UTC)
        dash.commits_last_7d = sum(1 for c in commits if (now - c.author_date).days <= 7)
        dash.commits_last_30d = sum(1 for c in commits if (now - c.author_date).days <= 30)
        dash.commits_last_90d = sum(1 for c in commits if (now - c.author_date).days <= 90)
        if commits:
            earliest = min(c.author_date for c in commits)
            weeks = max(1, (now - earliest).days // 7)
            dash.avg_commits_per_week = len(commits) / weeks
        # By-month histogram
        by_month: dict[str, int] = {}
        for c in commits:
            key = c.author_date.strftime("%Y-%m")
            by_month[key] = by_month.get(key, 0) + 1
        dash.by_month = sorted(
            ({"month": k, "commits": v} for k, v in by_month.items()),
            key=lambda x: x["month"],
        )
        # Bug trend (commits with 'fix' in message)
        bug_by_month: dict[str, int] = {}
        for c in commits:
            if re.search(r"\bfix\b|\bbug\b", c.message, re.I):
                key = c.author_date.strftime("%Y-%m")
                bug_by_month[key] = bug_by_month.get(key, 0) + 1
        dash.bug_trend = sorted(
            ({"month": k, "bug_fixes": v} for k, v in bug_by_month.items()),
            key=lambda x: x["month"],
        )
        # Feature growth (commits with 'feat' or 'feature')
        feat_by_month: dict[str, int] = {}
        for c in commits:
            if re.search(r"\bfeat\b|\bfeature\b", c.message, re.I):
                key = c.author_date.strftime("%Y-%m")
                feat_by_month[key] = feat_by_month.get(key, 0) + 1
        dash.feature_growth = sorted(
            ({"month": k, "features": v} for k, v in feat_by_month.items()),
            key=lambda x: x["month"],
        )
        # Technical debt trend (commits with 'debt', 'refactor', 'cleanup')
        debt_by_month: dict[str, int] = {}
        for c in commits:
            if re.search(r"\brefactor\b|\bdebt\b|\bcleanup\b", c.message, re.I):
                key = c.author_date.strftime("%Y-%m")
                debt_by_month[key] = debt_by_month.get(key, 0) + 1
        dash.technical_debt_trend = sorted(
            ({"month": k, "debt_commits": v} for k, v in debt_by_month.items()),
            key=lambda x: x["month"],
        )
        # Performance trend (commits with 'perf' or 'performance')
        perf_by_month: dict[str, int] = {}
        for c in commits:
            if re.search(r"\bperf\b|\bperformance\b|\boptimize\b", c.message, re.I):
                key = c.author_date.strftime("%Y-%m")
                perf_by_month[key] = perf_by_month.get(key, 0) + 1
        dash.performance_trend = sorted(
            ({"month": k, "perf_commits": v} for k, v in perf_by_month.items()),
            key=lambda x: x["month"],
        )
        return dash

    async def report(self) -> EvolutionReport:
        """Generate a full evolution report."""
        return EvolutionReport(
            repository=str(self._root),
            timeline=await self.timeline(limit=200),
            dashboard=await self.dashboard(),
            historical_comparisons=await self.historical_comparisons(),
        )

    async def historical_comparisons(self) -> list[dict[str, Any]]:
        """Compare the last 4 releases by commit count and time delta."""
        releases = await self._collect_releases()
        releases.sort(key=lambda r: r.date)
        if len(releases) < 2:
            return []
        out: list[dict[str, Any]] = []
        for i in range(1, len(releases)):
            prev = releases[i - 1]
            curr = releases[i]
            # Count commits between prev and curr dates via the _git helper
            log_text = self._git_run(
                [
                    "log",
                    "--oneline",
                    f"--since={prev.date.isoformat()}",
                    f"--until={curr.date.isoformat()}",
                ]
            )
            count = len([line for line in log_text.splitlines() if line.strip()])
            delta_days = (curr.date - prev.date).days
            out.append(
                {
                    "from": prev.tag,
                    "to": curr.tag,
                    "commits_between": count,
                    "days_between": delta_days,
                    "comparison": "faster"
                    if delta_days < 30
                    else "normal"
                    if delta_days < 90
                    else "slower",
                }
            )
        return out[-5:]

    # --- git helpers ----------------------------------------------------

    def _git_run(self, args: list[str]) -> str:
        """Run a read-only git command via the GitGateway (INV-02 compliant)."""
        return self._git.run(args)

    async def _collect_commits(self, limit: int = 500) -> list[CommitInfo]:
        commits: list[CommitInfo] = []
        # Use simpler log first
        log_text = self._git_run(
            [
                "log",
                f"-n{limit}",
                "--pretty=format:%H|%h|%an|%aI|%s",
            ]
        )
        if not log_text:
            return commits
        for line in log_text.splitlines():
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue
            commit_id, short, author, date_str, message = parts
            try:
                author_date = datetime.fromisoformat(date_str)
            except ValueError:
                continue
            is_merge = message.startswith("Merge ")
            is_breaking = bool(re.search(r"\bBREAKING\b|\bbreaking change\b", message, re.I))
            # Numstat for this commit
            numstat = self._git_run(["show", "--numstat", "--format=", commit_id])
            files_changed = 0
            insertions = 0
            deletions = 0
            for ns in numstat.splitlines():
                m = re.match(r"^(\d+|-)\s+(\d+|-)\s+(.+)$", ns)
                if m:
                    files_changed += 1
                    ins = m.group(1)
                    dels = m.group(2)
                    if ins != "-":
                        insertions += int(ins)
                    if dels != "-":
                        deletions += int(dels)
            commits.append(
                CommitInfo(
                    commit_id=commit_id,
                    short_hash=short,
                    author=author,
                    author_date=author_date,
                    message=message,
                    files_changed=files_changed,
                    insertions=insertions,
                    deletions=deletions,
                    is_merge=is_merge,
                    is_breaking=is_breaking,
                )
            )
        return commits

    async def _collect_branches(self) -> list[str]:
        out = self._git_run(["branch", "--list", "--all", "--format=%(refname:short)"])
        return [b.strip() for b in out.splitlines() if b.strip()]

    async def _collect_tags(self) -> list[str]:
        out = self._git_run(["tag", "--list"])
        return [t.strip() for t in out.splitlines() if t.strip()]

    async def _collect_releases(self) -> list[ReleaseInfo]:
        tags = await self._collect_tags()
        releases: list[ReleaseInfo] = []
        for tag in tags:
            # Get commit and date for the tag
            log = self._git_run(["log", "-1", "--pretty=format:%H|%aI", tag])
            if not log:
                continue
            parts = log.split("|", 1)
            if len(parts) < 2:
                continue
            commit, date_str = parts
            try:
                date = datetime.fromisoformat(date_str)
            except ValueError:
                date = datetime.now(UTC)
            is_pre = bool(re.match(r"^v?\d+\.\d+\.\d+(?:-|a|b|rc|alpha|beta)", tag, re.I))
            releases.append(
                ReleaseInfo(
                    tag=tag,
                    name=tag,
                    date=date,
                    commit=commit,
                    is_prerelease=is_pre,
                )
            )
        return releases

    def _safe_now_minus(self, days: int) -> datetime:
        return datetime.now(UTC) - timedelta(days=days)
