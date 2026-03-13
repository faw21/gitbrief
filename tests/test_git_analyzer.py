"""Tests for git_analyzer module."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gitbrief.git_analyzer import analyze_repo, _normalize, GitSummary, get_changed_files, get_diff


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


def test_get_changed_files_no_git(tmp_path):
    """Non-git directory returns empty set."""
    result = get_changed_files(tmp_path)
    assert result == set()


def test_get_changed_files_with_branch(tmp_path):
    """Repo with a feature branch returns changed files."""
    import subprocess

    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}

    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)

    # Initial commit on main
    (tmp_path / "base.py").write_text("x = 1")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, env=env)

    # Create feature branch and add a file
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, capture_output=True, env=env)
    (tmp_path / "new_feature.py").write_text("y = 2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "feat: add new feature"], cwd=tmp_path, capture_output=True, env=env)

    changed = get_changed_files(tmp_path, base_branch="main")
    assert "new_feature.py" in changed
    assert "base.py" not in changed


def test_get_diff_no_git(tmp_path):
    """Non-git directory returns empty string."""
    result = get_diff(tmp_path)
    assert result == ""


def test_get_diff_with_branch(tmp_path):
    """Repo with changes returns non-empty diff."""
    import subprocess

    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}

    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)

    # Initial commit on main
    (tmp_path / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, env=env)

    # Feature branch with change
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, capture_output=True, env=env)
    (tmp_path / "app.py").write_text("x = 1\ny = 2\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "add y"], cwd=tmp_path, capture_output=True, env=env)

    diff = get_diff(tmp_path, base_branch="main")
    assert "diff --git" in diff
    assert "+y = 2" in diff
