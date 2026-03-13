"""Git repository analysis for change-frequency and recency scoring."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from git import Repo, InvalidGitRepositoryError
    HAS_GIT = True
except ImportError:
    HAS_GIT = False


@dataclass(frozen=True)
class FileScore:
    """Relevance score for a single file."""

    path: str
    recency_score: float       # 0-1, how recently changed (1 = changed today)
    frequency_score: float     # 0-1, how often changed relative to repo max
    is_recently_changed: bool  # changed in last N commits
    last_modified_at: Optional[datetime] = None
    change_count: int = 0


@dataclass
class GitSummary:
    """Summary of recent git activity."""

    recent_commits: list[dict] = field(default_factory=list)
    active_authors: list[str] = field(default_factory=list)
    most_changed_files: list[str] = field(default_factory=list)
    branch: str = "unknown"
    total_commits_analyzed: int = 0


def _safe_branch(repo) -> str:
    try:
        return repo.active_branch.name
    except Exception:
        return "HEAD"


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Normalize a dict of floats to 0-1 range."""
    if not values:
        return {}
    max_val = max(values.values()) or 1.0
    return {k: v / max_val for k, v in values.items()}


def analyze_repo(repo_path: Path, max_commits: int = 100) -> tuple[dict[str, FileScore], GitSummary]:
    """
    Analyze a git repository and return per-file relevance scores.

    Returns:
        Tuple of (file_scores_dict, git_summary)
    """
    if not HAS_GIT:
        return {}, GitSummary()

    try:
        repo = Repo(repo_path, search_parent_directories=True)
    except (InvalidGitRepositoryError, Exception):
        return {}, GitSummary()

    # Collect commit data
    change_counts: dict[str, int] = {}
    last_seen: dict[str, datetime] = {}
    recent_threshold = max(1, max_commits // 5)  # top 20% of commits = "recent"
    recently_changed: set[str] = set()

    try:
        commits = list(repo.iter_commits(max_count=max_commits))
    except (ValueError, Exception):
        # Empty repo or no commits yet
        return {}, GitSummary(branch=_safe_branch(repo))
    summary = GitSummary(
        branch=_safe_branch(repo),
        total_commits_analyzed=len(commits),
    )

    author_counts: dict[str, int] = {}

    for idx, commit in enumerate(commits):
        commit_dt = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
        author = commit.author.name or "unknown"
        author_counts[author] = author_counts.get(author, 0) + 1

        try:
            changed_files = list(commit.stats.files.keys())
        except Exception:
            changed_files = []

        for fpath in changed_files:
            change_counts[fpath] = change_counts.get(fpath, 0) + 1
            if fpath not in last_seen or last_seen[fpath] < commit_dt:
                last_seen[fpath] = commit_dt
            if idx < recent_threshold:
                recently_changed.add(fpath)

        if idx < 20:
            summary.recent_commits.append({
                "sha": commit.hexsha[:8],
                "message": commit.message.strip().splitlines()[0][:80],
                "author": author,
                "date": commit_dt.isoformat(),
            })

    # Build summaries
    summary.active_authors = sorted(author_counts, key=lambda k: -author_counts[k])[:5]
    summary.most_changed_files = sorted(change_counts, key=lambda k: -change_counts[k])[:10]

    # Compute recency scores (how recently was each file last touched)
    now = datetime.now(tz=timezone.utc)
    raw_recency: dict[str, float] = {}
    for fpath, dt in last_seen.items():
        age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
        # Exponential decay: half-life = 30 days
        raw_recency[fpath] = 2 ** (-age_days / 30.0)

    recency_norm = _normalize(raw_recency)
    freq_norm = _normalize({k: float(v) for k, v in change_counts.items()})

    file_scores: dict[str, FileScore] = {}
    for fpath in set(change_counts) | set(last_seen):
        file_scores[fpath] = FileScore(
            path=fpath,
            recency_score=recency_norm.get(fpath, 0.0),
            frequency_score=freq_norm.get(fpath, 0.0),
            is_recently_changed=fpath in recently_changed,
            last_modified_at=last_seen.get(fpath),
            change_count=change_counts.get(fpath, 0),
        )

    return file_scores, summary
