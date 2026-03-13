"""Tests for renderer module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gitbrief.git_analyzer import GitSummary
from gitbrief.renderer import render_context, _lang, _render_xml
from gitbrief.token_budget import BudgetAllocation


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
    assert "gitbrief" in doc
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


# ── XML format tests ──────────────────────────────────────────────────────────

def test_render_xml_basic_structure(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary(branch="main", total_commits_analyzed=5)
    doc = render_context(tmp_path, [], summary, alloc, repo_name="myrepo", fmt="xml")
    assert '<?xml version="1.0"' in doc
    assert 'repo="myrepo"' in doc
    assert "<token_budget" in doc
    assert "<git_activity" in doc


def test_render_xml_file_contents(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    rf = _make_rf("main.py", is_recently_changed=True)
    rf.priority = 0.95
    alloc = _make_allocation(files_included=1)
    summary = GitSummary()
    selected = [(rf, "x = 1", 5)]
    doc = render_context(tmp_path, selected, summary, alloc, fmt="xml")
    assert "<documents>" in doc
    assert '<document index="1"' in doc
    assert "recently_changed" in doc
    assert "<source>main.py</source>" in doc
    assert "<document_content>" in doc
    assert "x = 1" in doc


def test_render_xml_no_git_history(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary(total_commits_analyzed=0)
    doc = render_context(tmp_path, [], summary, alloc, fmt="xml")
    assert "<git_activity" not in doc


def test_render_xml_git_summary(tmp_path):
    summary = GitSummary(
        branch="feature-x",
        total_commits_analyzed=10,
        active_authors=["Alice"],
        most_changed_files=["main.py"],
        recent_commits=[
            {"sha": "abc123", "message": "fix bug", "author": "Alice", "date": "2026-01-01T00:00:00+00:00"}
        ],
    )
    alloc = _make_allocation()
    doc = render_context(tmp_path, [], summary, alloc, fmt="xml")
    assert 'branch="feature-x"' in doc
    assert "<author>Alice</author>" in doc
    assert "fix bug" in doc
    assert "<file>main.py</file>" in doc


def test_render_xml_default_format_is_markdown(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc, repo_name="test")
    # Default should be markdown, not XML
    assert "# Codebase Context: test" in doc
    assert "<?xml" not in doc


# ── --prompt tests ────────────────────────────────────────────────────────────

def test_render_prompt_appended_markdown(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc, prompt="Review for security issues")
    assert "## Instruction" in doc
    assert "Review for security issues" in doc
    # Instruction comes after the main content
    assert doc.index("## Instruction") > doc.index("# Codebase Context")


def test_render_prompt_appended_xml(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc, fmt="xml", prompt="Find all TODO comments")
    # XML body comes first, then the instruction appended as plain text
    assert "Find all TODO comments" in doc
    xml_end = doc.index("</codebase_context>")
    prompt_pos = doc.index("Find all TODO comments")
    assert prompt_pos > xml_end


def test_render_no_prompt_no_instruction_section(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc)
    assert "## Instruction" not in doc


# ── --tree tests ──────────────────────────────────────────────────────────────

def test_render_tree_markdown(tmp_path):
    rf1 = _make_rf("src/main.py")
    rf2 = _make_rf("src/utils.py")
    rf3 = _make_rf("README.md")
    alloc = _make_allocation(files_included=3)
    summary = GitSummary()
    selected = [(rf1, "x=1", 5), (rf2, "y=2", 5), (rf3, "# hi", 5)]
    doc = render_context(tmp_path, selected, summary, alloc, include_tree=True)
    assert "## Directory Structure" in doc
    assert "src/" in doc
    assert "main.py" in doc
    assert "README.md" in doc


def test_render_tree_xml(tmp_path):
    rf1 = _make_rf("app/models.py")
    rf1.priority = 0.85
    rf2 = _make_rf("app/views.py")
    rf2.priority = 0.80
    alloc = _make_allocation(files_included=2)
    summary = GitSummary()
    selected = [(rf1, "class M: pass", 10), (rf2, "class V: pass", 10)]
    doc = render_context(tmp_path, selected, summary, alloc, fmt="xml", include_tree=True)
    assert "<directory_tree>" in doc
    assert "app/" in doc


def test_render_no_tree_by_default(tmp_path):
    alloc = _make_allocation()
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc)
    assert "## Directory Structure" not in doc


def test_render_tree_empty_files(tmp_path):
    """Tree with no files should not crash."""
    alloc = _make_allocation()
    summary = GitSummary()
    doc = render_context(tmp_path, [], summary, alloc, include_tree=True)
    # No files means no tree section
    assert "## Directory Structure" not in doc
