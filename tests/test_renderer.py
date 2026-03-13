"""Tests for renderer module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codebrief.git_analyzer import GitSummary
from codebrief.renderer import render_context, _lang
from codebrief.token_budget import BudgetAllocation


def _make_allocation(**kwargs):
    defaults = dict(
        total_budget=8000, header_tokens=500, git_summary_tokens=800,
        files_tokens=1000, files_included=2, files_skipped=3, budget_used=2300,
    )
    defaults.update(kwargs)
    return BudgetAllocation(**defaults)


def _make_rf(relative_path: str, is_recently_changed: bool = False):
    rf = MagicMock()
    rf.relative_path = relative_path
    rf.path = Path(relative_path)
    rf.is_recently_changed = is_recently_changed
    return rf


def test_render_basic_structure(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary(branch="main", total_commits_analyzed=5)
    selected = []
    doc = render_context(tmp_path, selected, summary, alloc, repo_name="myrepo")
    assert "# Codebase Context: myrepo" in doc
    assert "codebrief" in doc
    assert "Token budget" in doc


def test_render_includes_git_summary(tmp_path):
    summary = GitSummary(
        branch="feature-x",
        total_commits_analyzed=10,
        active_authors=["Alice", "Bob"],
        most_changed_files=["main.py", "utils.py"],
        recent_commits=[
            {"sha": "abc123", "message": "fix bug", "author": "Alice", "date": "2026-01-01T00:00:00+00:00"}
        ],
    )
    alloc = _make_allocation()
    doc = render_context(tmp_path, [], summary, alloc)
    assert "feature-x" in doc
    assert "Alice" in doc
    assert "fix bug" in doc
    assert "main.py" in doc


def test_render_no_git_history(tmp_path):
    summary = GitSummary(total_commits_analyzed=0)
    alloc = _make_allocation()
    doc = render_context(tmp_path, [], summary, alloc)
    # Should not include git section
    assert "Repository Activity" not in doc


def test_render_recently_changed_flag(tmp_path):
    (tmp_path / "hot.py").write_text("x = 1")
    rf = _make_rf("hot.py", is_recently_changed=True)
    alloc = _make_allocation(files_included=1, files_skipped=0)
    summary = GitSummary()
    selected = [(rf, "x = 1", 5)]
    doc = render_context(tmp_path, selected, summary, alloc)
    assert "🔥" in doc
    assert "recently changed" in doc


def test_render_file_contents_included(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    rf = _make_rf("app.py")
    alloc = _make_allocation(files_included=1)
    summary = GitSummary()
    selected = [(rf, "print('hello')", 10)]
    doc = render_context(tmp_path, selected, summary, alloc)
    assert "print('hello')" in doc
    assert "```python" in doc


def test_lang_detection():
    assert _lang(Path("foo.py")) == "python"
    assert _lang(Path("app.ts")) == "typescript"
    assert _lang(Path("Dockerfile")) == "dockerfile"
    assert _lang(Path("data.yaml")) == "yaml"
    assert _lang(Path("unknown.xyz")) == ""


def test_render_allocation_stats(tmp_path):
    alloc = _make_allocation(budget_used=7500, total_budget=8000, files_included=5, files_skipped=2)
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc)
    assert "7,500" in doc  # budget_used
    assert "8,000" in doc  # total_budget
    assert "5" in doc      # files_included
