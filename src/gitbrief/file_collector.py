"""File collection, filtering, and relevance-based ranking."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pathspec

from .git_analyzer import FileScore


# Files to always skip
_ALWAYS_SKIP_NAMES = {
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox",
    "venv", ".venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "coverage", ".coverage",
}

_ALWAYS_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".avi",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib",
    ".woff", ".woff2", ".ttf", ".eot",
    ".lock",  # lock files add noise
}

# Configurable binary/noise extensions
_NOISE_EXTENSIONS = {
    ".min.js", ".min.css",
    ".map",
}

# Default important file patterns (boosted priority)
_HIGH_PRIORITY_GLOBS = [
    "README*", "CONTRIBUTING*", "ARCHITECTURE*", "DESIGN*",
    "*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
    "*.go", "*.rs", "*.java", "*.kt", "*.swift",
    "*.rb", "*.php", "*.c", "*.cpp", "*.h", "*.hpp",
    "Makefile", "Dockerfile", "docker-compose*",
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
]


@dataclass(frozen=True)
class RankedFile:
    """A file with its computed priority score."""

    path: Path
    relative_path: str
    priority: float           # 0-1 combined score
    token_estimate: int       # rough token count
    is_recently_changed: bool
    git_change_count: int
    is_config: bool
    is_test: bool


def _load_gitignore(repo_root: Path) -> Optional[pathspec.PathSpec]:
    gi_path = repo_root / ".gitignore"
    if gi_path.exists():
        lines = gi_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    return None


def _is_binary(path: Path) -> bool:
    """Quick check: read first 1024 bytes and look for null bytes."""
    try:
        chunk = path.read_bytes()[:1024]
        return b"\x00" in chunk
    except Exception:
        return True


def _token_estimate(path: Path) -> int:
    """Rough token estimate: ~1 token per 4 chars (GPT-style)."""
    try:
        size = path.stat().st_size
        return max(1, size // 4)
    except Exception:
        return 0


def _priority_score(
    rel_path: str,
    git_score: Optional[FileScore],
    is_config: bool,
    is_test: bool,
    name_lower: str,
) -> float:
    """Compute a 0-1 priority score for a file."""
    score = 0.2  # baseline

    # Git signals (up to 0.5)
    if git_score is not None:
        git_weight = 0.6 * git_score.recency_score + 0.4 * git_score.frequency_score
        if git_score.is_recently_changed:
            git_weight = min(1.0, git_weight + 0.2)
        score += 0.5 * git_weight

    # Config / entry-point boost
    if is_config:
        score += 0.15

    # README / doc boost
    if name_lower.startswith("readme") or name_lower.startswith("contributing"):
        score += 0.1

    # Test files get slight penalty (useful but lower priority than impl)
    if is_test:
        score -= 0.05

    return min(1.0, max(0.0, score))


def collect_files(
    repo_root: Path,
    file_scores: dict[str, FileScore],
    max_files: int = 200,
    include_tests: bool = True,
) -> list[RankedFile]:
    """
    Walk the repo, filter, score, and return a ranked list of files.
    """
    gitignore = _load_gitignore(repo_root)
    ranked: list[RankedFile] = []

    config_names = {
        "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "cargo.toml", "go.mod", "go.sum",
        "makefile", "dockerfile", "docker-compose.yml",
        ".env.example", ".env.sample",
    }

    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in _ALWAYS_SKIP_NAMES and not d.startswith(".")
        ]

        for fname in filenames:
            abs_path = Path(dirpath) / fname
            rel = abs_path.relative_to(repo_root)
            rel_str = str(rel)

            # Extension filters
            suffix = abs_path.suffix.lower()
            if suffix in _ALWAYS_SKIP_EXTENSIONS:
                continue
            if abs_path.name.lower().endswith((".min.js", ".min.css", ".map")):
                continue

            # Gitignore
            if gitignore and gitignore.match_file(rel_str):
                continue

            # Binary check
            if _is_binary(abs_path):
                continue

            name_lower = fname.lower()
            is_test = (
                "test" in name_lower
                or "spec" in name_lower
                or any(part in ("tests", "test", "__tests__", "spec") for part in rel.parts)
            )
            is_config = name_lower in config_names or suffix in (".toml", ".yaml", ".yml", ".json", ".cfg", ".ini")

            if not include_tests and is_test:
                continue

            git_score = file_scores.get(rel_str)
            priority = _priority_score(rel_str, git_score, is_config, is_test, name_lower)
            tokens = _token_estimate(abs_path)

            ranked.append(RankedFile(
                path=abs_path,
                relative_path=rel_str,
                priority=priority,
                token_estimate=tokens,
                is_recently_changed=git_score.is_recently_changed if git_score else False,
                git_change_count=git_score.change_count if git_score else 0,
                is_config=is_config,
                is_test=is_test,
            ))

    # Sort by priority descending
    ranked.sort(key=lambda f: -f.priority)
    return ranked[:max_files]
