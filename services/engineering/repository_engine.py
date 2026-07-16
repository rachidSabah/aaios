"""Repository Intelligence Engine — discovers, analyzes, and graphs repositories.

Phase 2-3: Repository Intelligence + Repository Knowledge Graph.

Discovers repositories (monorepo, polyrepo, nested, submodules), analyzes
source files (AST-based for Python, regex-based for others), builds a
knowledge graph of modules/classes/functions/dependencies, and detects
architecture issues.

Everything is read-only. Never modifies code.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from pathlib import Path

from core.logging import get_logger
from services.engineering.models import (
    ArchRecommendation,
    FileAnalysis,
    LanguageType,
    RepositoryAnalysis,
    RepositoryInfo,
    RepositoryIssue,
)

_log = get_logger(__name__)

__all__ = [
    "ArchitectureIntelligenceEngine",
    "CodeIntelligenceEngine",
    "RepositoryIntelligenceEngine",
]


# File extension → language mapping
EXT_TO_LANG: dict[str, str] = {
    ".py": LanguageType.PYTHON.value,
    ".ts": LanguageType.TYPESCRIPT.value,
    ".tsx": LanguageType.TYPESCRIPT.value,
    ".js": LanguageType.JAVASCRIPT.value,
    ".jsx": LanguageType.JAVASCRIPT.value,
    ".go": LanguageType.GO.value,
    ".rs": LanguageType.RUST.value,
    ".java": LanguageType.JAVA.value,
    ".cs": LanguageType.CSHARP.value,
    ".cpp": LanguageType.CPP.value,
    ".cc": LanguageType.CPP.value,
    ".cxx": LanguageType.CPP.value,
    ".kt": LanguageType.KOTLIN.value,
    ".swift": LanguageType.SWIFT.value,
    ".php": LanguageType.PHP.value,
    ".rb": LanguageType.RUBY.value,
    ".sh": LanguageType.SHELL.value,
    ".ps1": LanguageType.POWERSHELL.value,
    ".yaml": LanguageType.YAML.value,
    ".yml": LanguageType.YAML.value,
    ".json": LanguageType.JSON.value,
    ".md": LanguageType.MARKDOWN.value,
    ".html": LanguageType.HTML.value,
    ".css": LanguageType.CSS.value,
    ".sql": LanguageType.SQL.value,
}

# Directories to skip during analysis
SKIP_DIRS: set[str] = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", "dist", "build", ".next", "out",
    ".tox", ".eggs", "*.egg-info", "coverage", ".coverage",
}


class RepositoryIntelligenceEngine:
    """Discovers and analyzes repositories.

    Phase 2: Repository Intelligence Engine.
    """

    def __init__(self, root_path: Path | str = ".") -> None:
        self._root = Path(root_path)

    async def discover_repositories(self) -> list[RepositoryInfo]:
        """Discover all repositories in the root path."""
        repos: list[RepositoryInfo] = []
        # Check if root is a git repo
        if (self._root / ".git").exists():
            repos.append(await self._analyze_repo(self._root, is_main=True))
        # Find nested repos (submodules, worktrees)
        for git_dir in self._root.rglob(".git"):
            if git_dir == self._root / ".git":
                continue
            repo_path = git_dir.parent
            if any(skip in str(repo_path) for skip in SKIP_DIRS):
                continue
            repos.append(await self._analyze_repo(repo_path, is_main=False))
        return repos

    async def _analyze_repo(self, path: Path, *, is_main: bool = False) -> RepositoryInfo:
        """Analyze a single repository."""
        info = RepositoryInfo(
            path=str(path),
            name=path.name,
            is_main=is_main,
            repo_type="monorepo" if is_main else "submodule",
        )
        # Count files and lines
        lang_counts: Counter[str] = Counter()
        for ext, lang in EXT_TO_LANG.items():
            for file_path in path.rglob(f"*{ext}"):
                if any(skip in str(file_path) for skip in SKIP_DIRS):
                    continue
                info.file_count += 1
                try:
                    lines = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
                    info.line_count += lines
                    lang_counts[lang] += lines
                except Exception:
                    pass
        info.language_breakdown = dict(lang_counts.most_common(10))
        return info

    async def analyze(self) -> RepositoryAnalysis:
        """Full repository analysis."""
        analysis = RepositoryAnalysis()
        repos = await self.discover_repositories()
        analysis.repos = repos
        for repo in repos:
            analysis.total_files += repo.file_count
            analysis.total_lines += repo.line_count
        # Deep analysis (AST for Python files)
        for py_file in self._root.rglob("*.py"):
            if any(skip in str(py_file) for skip in SKIP_DIRS):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        analysis.total_classes += 1
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        analysis.total_functions += 1
            except Exception:
                pass
        # Count test files
        test_dir = self._root / "tests"
        if test_dir.exists():
            analysis.total_tests = len(list(test_dir.rglob("*.py")))
        # Detect issues
        analysis.issues = await self._detect_issues()
        # Health score
        score = 100.0
        for issue in analysis.issues:
            if issue.severity == "critical":
                score -= 10
            elif issue.severity == "high":
                score -= 5
            elif issue.severity == "medium":
                score -= 2
            else:
                score -= 0.5
        analysis.health_score = max(0.0, score)
        return analysis

    async def _detect_issues(self) -> list[RepositoryIssue]:
        """Detect repository issues."""
        issues: list[RepositoryIssue] = []
        src_dirs = [self._root / "services", self._root / "core", self._root / "agents",
                     self._root / "supervisor", self._root / "orchestrator", self._root / "surfaces"]
        for src_dir in src_dirs:
            if not src_dir.exists():
                continue
            for py_file in src_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                test_name = f"test_{py_file.stem}.py"
                if not (self._root / "tests" / "unit" / test_name).exists():
                    issues.append(RepositoryIssue(
                        issue_type="missing_test",
                        severity="medium",
                        file=str(py_file.relative_to(self._root)),
                        description=f"No test file for {py_file.name}",
                        recommendation=f"Create {test_name}",
                    ))
        # Check for missing docstrings
        for py_file in self._root.rglob("*.py"):
            if any(skip in str(py_file) for skip in SKIP_DIRS) or "tests/" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and not ast.get_docstring(node):
                        issues.append(RepositoryIssue(
                            issue_type="missing_doc",
                            severity="low",
                            file=str(py_file.relative_to(self._root)),
                            line=node.lineno,
                            description=f"Class '{node.name}' has no docstring",
                            recommendation="Add a docstring",
                        ))
            except Exception:
                pass
        return issues[:50]


class CodeIntelligenceEngine:
    """Analyzes source code at the AST level.

    Phase 4: Code Intelligence Engine.
    """

    async def analyze_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a single source file."""
        analysis = FileAnalysis(file_path=str(file_path))
        ext = file_path.suffix.lower()
        analysis.language = EXT_TO_LANG.get(ext, "unknown")
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return analysis
        analysis.line_count = len(source.splitlines())
        if ext == ".py":
            await self._analyze_python(source, analysis)
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            await self._analyze_javascript(source, analysis)
        elif ext == ".go":
            await self._analyze_go(source, analysis)
        else:
            await self._analyze_generic(source, analysis)
        # Compute metrics
        analysis.complexity_score = self._compute_complexity(source, analysis.language)
        analysis.maintainability_score = max(0.0, 1.0 - analysis.complexity_score)
        return analysis

    async def _analyze_python(self, source: str, analysis: FileAnalysis) -> None:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    analysis.classes.append(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    analysis.functions.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis.imports.append(node.module)
        except Exception:
            pass

    async def _analyze_javascript(self, source: str, analysis: FileAnalysis) -> None:
        import re
        # Extract classes
        analysis.classes = re.findall(r"class\s+(\w+)", source)
        # Extract functions
        analysis.functions = re.findall(r"function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(", source)
        analysis.functions = [f for pair in analysis.functions for f in pair if f]
        # Extract imports
        analysis.imports = re.findall(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", source)

    async def _analyze_go(self, source: str, analysis: FileAnalysis) -> None:
        import re
        analysis.functions = re.findall(r"func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(", source)
        analysis.imports = re.findall(r"\"([^\"]+)\"", source)

    async def _analyze_generic(self, source: str, analysis: FileAnalysis) -> None:
        import re
        # Generic function detection
        analysis.functions = re.findall(r"def\s+(\w+)|function\s+(\w+)", source)
        analysis.functions = [f for pair in analysis.functions for f in pair if f]

    def _compute_complexity(self, source: str, language: str) -> float:
        """Compute cyclomatic complexity (simplified)."""
        import re
        if language == "python":
            branches = len(re.findall(r"\b(if|elif|for|while|except|and|or)\b", source))
        else:
            branches = len(re.findall(r"\b(if|for|while|catch|&&|\|\|)\b", source))
        lines = max(1, len(source.splitlines()))
        return min(1.0, branches / max(1, lines / 10))


class ArchitectureIntelligenceEngine:
    """Inspects architecture and detects violations.

    Phase 5: Architecture Intelligence.
    Read-only — generates recommendations only, never modifies code.
    """

    def __init__(self, root_path: Path | str = ".") -> None:
        self._root = Path(root_path)

    async def inspect(self) -> list[ArchRecommendation]:
        """Inspect architecture and generate recommendations."""
        recs: list[ArchRecommendation] = []
        recs.extend(await self._detect_layer_violations())
        recs.extend(await self._detect_circular_dependencies())
        recs.extend(await self._detect_missing_tests())
        return recs

    async def _detect_layer_violations(self) -> list[ArchRecommendation]:
        """Detect layer violations (e.g., L3 importing from L5)."""
        recs: list[ArchRecommendation] = []
        layer_map: dict[str, str] = {
            "core": "L1", "services": "L2", "agents": "L3",
            "supervisor": "L4", "orchestrator": "L4", "surfaces": "L5",
        }
        for src_dir, src_layer in layer_map.items():
            dir_path = self._root / src_dir
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in SKIP_DIRS):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            for target_dir, target_layer in layer_map.items():
                                if target_dir == src_dir:
                                    continue
                                if node.module.startswith(target_dir) or node.module.startswith(f"{target_dir}."):
                                    # Check if this is a violation (higher layer importing lower is OK)
                                    src_num = int(src_layer[1:])
                                    tgt_num = int(target_layer[1:])
                                    if tgt_num > src_num:
                                        recs.append(ArchRecommendation(
                                            title=f"Layer violation: {src_dir} imports from {target_dir}",
                                            description=f"{py_file.relative_to(self._root)} imports from {node.module} "
                                                        f"({src_layer} → {target_layer}). Lower layers should not import from higher layers.",
                                            recommendation_type="layer_violation",
                                            confidence=0.8,
                                            risk="medium",
                                            impact=0.6,
                                            affected_files=[str(py_file.relative_to(self._root))],
                                            reasoning=f"Layer {src_layer} ({src_dir}) should not depend on layer {target_layer} ({target_dir}). "
                                                      f"This creates unwanted coupling.",
                                            supporting_evidence={"source_layer": src_layer, "target_layer": target_layer, "import": node.module},
                                            estimated_effort_hours=2.0,
                                            rollback_strategy="Revert the import and refactor to use an interface or event.",
                                        ))
                                        break
                except Exception:
                    pass
        return recs[:20]

    async def _detect_circular_dependencies(self) -> list[ArchRecommendation]:
        """Detect circular dependencies between modules."""
        recs: list[ArchRecommendation] = []
        # Build dependency graph
        deps: dict[str, set[str]] = defaultdict(set)
        for src_dir in ["core", "services", "agents", "supervisor", "orchestrator", "surfaces"]:
            dir_path = self._root / src_dir
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                if any(skip in str(py_file) for skip in SKIP_DIRS):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(source)
                    module_name = str(py_file.relative_to(self._root)).replace("/", ".").replace(".py", "")
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            deps[module_name].add(node.module)
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                deps[module_name].add(alias.name)
                except Exception:
                    pass
        # Simple cycle detection (A imports B, B imports A)
        checked: set[tuple[str, str]] = set()
        for mod_a, mod_a_deps in deps.items():
            for dep in mod_a_deps:
                if (dep, mod_a) in checked:
                    continue
                checked.add((mod_a, dep))
                if dep in deps and mod_a in deps[dep]:
                    recs.append(ArchRecommendation(
                        title=f"Circular dependency: {mod_a} ↔ {dep}",
                        description=f"{mod_a} imports {dep} and {dep} imports {mod_a}.",
                        recommendation_type="circular_dependency",
                        confidence=0.7,
                        risk="high",
                        impact=0.7,
                        affected_files=[mod_a, dep],
                        reasoning="Circular dependencies make modules hard to test, maintain, and reason about independently.",
                        supporting_evidence={"module_a": mod_a, "module_b": dep},
                        estimated_effort_hours=4.0,
                        rollback_strategy="Extract shared logic into a third module that both can depend on.",
                    ))
        return recs[:10]

    async def _detect_missing_tests(self) -> list[ArchRecommendation]:
        """Detect modules without test coverage."""
        recs: list[ArchRecommendation] = []
        src_dirs = [self._root / "services", self._root / "core", self._root / "agents"]
        for src_dir in src_dirs:
            if not src_dir.exists():
                continue
            for py_file in src_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                test_name = f"test_{py_file.stem}.py"
                if not (self._root / "tests" / "unit" / test_name).exists():
                    recs.append(ArchRecommendation(
                        title=f"Missing tests: {py_file.name}",
                        description=f"No test file found for {py_file.relative_to(self._root)}",
                        recommendation_type="missing_tests",
                        confidence=0.9,
                        risk="low",
                        impact=0.5,
                        affected_files=[str(py_file.relative_to(self._root))],
                        reasoning="Untested code is more likely to contain bugs and regressions.",
                        supporting_evidence={"file": str(py_file.relative_to(self._root))},
                        estimated_effort_hours=2.0,
                        rollback_strategy="Simply delete the test file if not needed.",
                    ))
        return recs[:20]
