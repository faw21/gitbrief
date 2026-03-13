"""Tests for git_analyzer module."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codebrief.git_analyzer import analyze_repo, _normalize, GitSummary


def test_normalize_empty():
    assert _normalize({}) == {}


def test_normalize_single():
    result = _normalize({"a": 10.0})
    assert result["a"] == 1.0


def test_normalize_multiple():
    result = _normalize({"a": 5.0, "b": 10.0, "c": 2.5})
    assert result["b"] == 1.0
    assert result["a"] == pytest.approx(0.5)
    assert result["c"] == pytest.approx(0.25)


def test_normalize_all_zeros():
    # All zeros → max is 0, should not divide by zero
    result = _normalize({"a": 0.0, "b": 0.0})
    assert result["a"] == 0.0
    assert result["b"] == 0.0


def test_analyze_repo_no_git(tmp_path):
    """Non-git directory returns empty scores and empty summary."""
    scores, summary = analyze_repo(tmp_path)
    assert scores == {}
    assert isinstance(summary, GitSummary)
    assert summary.total_commits_analyzed == 0


def test_analyze_repo_empty_git(tmp_path):
    """Freshly initialized git repo with no commits returns gracefully."""
    import subprocess
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    scores, summary = analyze_repo(tmp_path)
    assert scores == {}
    assert summary.total_commits_analyzed == 0


def test_analyze_repo_with_commits(tmp_path):
    """Repo with commits returns file scores."""
    import subprocess

    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}

    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)

    # Create and commit a file
    f = tmp_path / "main.py"
    f.write_text("print('hello')")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True, env=env)

    scores, summary = analyze_repo(tmp_path)
    assert "main.py" in scores
    assert scores["main.py"].change_count == 1
    assert scores["main.py"].recency_score > 0
    assert summary.total_commits_analyzed == 1
    assert "main.py" in summary.most_changed_files
