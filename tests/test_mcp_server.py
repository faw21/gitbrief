"""Tests for the gitbrief MCP server."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_summary():
    summary = MagicMock()
    summary.branch = "main"
    summary.total_commits_analyzed = 10
    summary.recent_commits = [
        {"sha": "abc123", "message": "feat: add feature", "author": "Alice", "date": "2026-03-13T00:00:00+00:00"},
    ]
    summary.most_changed_files = ["src/main.py", "src/utils.py"]
    summary.active_authors = ["Alice", "Bob"]
    return summary


def _make_mock_file_score(path="src/main.py", priority=0.9, recently_changed=True):
    fs = MagicMock()
    fs.relative_path = path
    fs.priority = priority
    fs.is_recently_changed = recently_changed
    return fs


# ---------------------------------------------------------------------------
# Tests: pack_context
# ---------------------------------------------------------------------------

class TestPackContext:
    def test_nonexistent_path_returns_error(self):
        from gitbrief.mcp_server import pack_context
        result = pack_context(path="/nonexistent/path/xyz")
        assert "Error" in result
        assert "does not exist" in result

    @patch("gitbrief.mcp_server.analyze_repo")
    @patch("gitbrief.mcp_server.collect_files")
    @patch("gitbrief.mcp_server.fit_files_to_budget")
    @patch("gitbrief.mcp_server.render_context")
    def test_pack_context_returns_document(
        self, mock_render, mock_fit, mock_collect, mock_analyze, tmp_path
    ):
        from gitbrief.mcp_server import pack_context

        # Create a fake git repo
        (tmp_path / ".git").mkdir()

        mock_summary = _make_mock_summary()
        mock_analyze.return_value = ({}, mock_summary)
        mock_collect.return_value = []

        mock_alloc = MagicMock()
        mock_fit.return_value = ([], mock_alloc)
        mock_render.return_value = "# My context doc"

        result = pack_context(path=str(tmp_path), budget=8000)

        assert result == "# My context doc"
        mock_analyze.assert_called_once()
        mock_render.assert_called_once()

    @patch("gitbrief.mcp_server.analyze_repo")
    @patch("gitbrief.mcp_server.collect_files")
    @patch("gitbrief.mcp_server.get_changed_files")
    @patch("gitbrief.mcp_server.fit_files_to_budget")
    @patch("gitbrief.mcp_server.render_context")
    def test_changed_only_filters_files(
        self, mock_render, mock_fit, mock_get_changed, mock_collect, mock_analyze, tmp_path
    ):
        from gitbrief.mcp_server import pack_context

        (tmp_path / ".git").mkdir()

        mock_summary = _make_mock_summary()
        mock_analyze.return_value = ({}, mock_summary)

        file1 = _make_mock_file_score("src/main.py")
        file2 = _make_mock_file_score("src/utils.py")
        mock_collect.return_value = [file1, file2]
        mock_get_changed.return_value = {"src/main.py"}  # only main.py changed

        mock_alloc = MagicMock()
        mock_fit.return_value = ([file1], mock_alloc)
        mock_render.return_value = "# filtered doc"

        result = pack_context(path=str(tmp_path), changed_only=True)

        assert result == "# filtered doc"
        # fit_files_to_budget should receive only the changed file
        call_args = mock_fit.call_args[0]
        assert len(call_args[0]) == 1
        assert call_args[0][0].relative_path == "src/main.py"

    @patch("gitbrief.mcp_server.analyze_repo")
    def test_exception_returns_error_string(self, mock_analyze, tmp_path):
        from gitbrief.mcp_server import pack_context

        (tmp_path / ".git").mkdir()
        mock_analyze.side_effect = RuntimeError("git exploded")

        result = pack_context(path=str(tmp_path))
        assert "Error" in result
        assert "git exploded" in result


# ---------------------------------------------------------------------------
# Tests: get_repo_summary
# ---------------------------------------------------------------------------

class TestGetRepoSummary:
    def test_nonexistent_path_returns_error(self):
        from gitbrief.mcp_server import get_repo_summary
        result = get_repo_summary(path="/nonexistent/xyz")
        assert "Error" in result

    @patch("gitbrief.mcp_server.analyze_repo")
    def test_returns_markdown_summary(self, mock_analyze, tmp_path):
        from gitbrief.mcp_server import get_repo_summary

        (tmp_path / ".git").mkdir()
        mock_summary = _make_mock_summary()
        mock_analyze.return_value = ({}, mock_summary)

        result = get_repo_summary(path=str(tmp_path))

        assert "# Repository Summary" in result
        assert "main" in result
        assert "abc123" in result
        assert "Alice" in result
        assert "src/main.py" in result

    @patch("gitbrief.mcp_server.analyze_repo")
    def test_exception_returns_error_string(self, mock_analyze, tmp_path):
        from gitbrief.mcp_server import get_repo_summary

        (tmp_path / ".git").mkdir()
        mock_analyze.side_effect = ValueError("oops")

        result = get_repo_summary(path=str(tmp_path))
        assert "Error" in result


# ---------------------------------------------------------------------------
# Tests: list_repo_files
# ---------------------------------------------------------------------------

class TestListRepoFiles:
    def test_nonexistent_path_returns_error(self):
        from gitbrief.mcp_server import list_repo_files
        result = list_repo_files(path="/nonexistent/xyz")
        assert "Error" in result

    @patch("gitbrief.mcp_server.analyze_repo")
    @patch("gitbrief.mcp_server.collect_files")
    def test_returns_markdown_table(self, mock_collect, mock_analyze, tmp_path):
        from gitbrief.mcp_server import list_repo_files

        (tmp_path / ".git").mkdir()
        mock_summary = _make_mock_summary()
        mock_analyze.return_value = ({}, mock_summary)

        file1 = _make_mock_file_score("src/main.py", priority=0.9, recently_changed=True)
        file2 = _make_mock_file_score("src/utils.py", priority=0.5, recently_changed=False)
        mock_collect.return_value = [file1, file2]

        result = list_repo_files(path=str(tmp_path))

        assert "| File |" in result
        assert "src/main.py" in result
        assert "src/utils.py" in result
        assert "🔥 Yes" in result
        assert "No" in result

    @patch("gitbrief.mcp_server.analyze_repo")
    @patch("gitbrief.mcp_server.collect_files")
    def test_empty_files_returns_message(self, mock_collect, mock_analyze, tmp_path):
        from gitbrief.mcp_server import list_repo_files

        (tmp_path / ".git").mkdir()
        mock_summary = _make_mock_summary()
        mock_analyze.return_value = ({}, mock_summary)
        mock_collect.return_value = []

        result = list_repo_files(path=str(tmp_path))
        assert "No files found" in result

    @patch("gitbrief.mcp_server.analyze_repo")
    @patch("gitbrief.mcp_server.collect_files")
    @patch("gitbrief.mcp_server.get_changed_files")
    def test_changed_only_filters(self, mock_changed, mock_collect, mock_analyze, tmp_path):
        from gitbrief.mcp_server import list_repo_files

        (tmp_path / ".git").mkdir()
        mock_summary = _make_mock_summary()
        mock_analyze.return_value = ({}, mock_summary)

        file1 = _make_mock_file_score("src/main.py")
        file2 = _make_mock_file_score("src/utils.py")
        mock_collect.return_value = [file1, file2]
        mock_changed.return_value = {"src/main.py"}

        result = list_repo_files(path=str(tmp_path), changed_only=True)

        assert "src/main.py" in result
        assert "src/utils.py" not in result

    @patch("gitbrief.mcp_server.analyze_repo")
    def test_exception_returns_error(self, mock_analyze, tmp_path):
        from gitbrief.mcp_server import list_repo_files

        (tmp_path / ".git").mkdir()
        mock_analyze.side_effect = Exception("broken")

        result = list_repo_files(path=str(tmp_path))
        assert "Error" in result


# ---------------------------------------------------------------------------
# Tests: MCP server registration
# ---------------------------------------------------------------------------

class TestMCPRegistration:
    def test_all_tools_registered(self):
        from gitbrief.mcp_server import mcp
        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        assert "pack_context" in tool_names
        assert "get_repo_summary" in tool_names
        assert "list_repo_files" in tool_names

    def test_run_function_exists(self):
        from gitbrief.mcp_server import run
        assert callable(run)
