"""Integration tests for the CLI."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from gitbrief.cli import main, _copy_to_clipboard


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo with some files and a commit."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    (tmp_path / "main.py").write_text("x = 1\n")
    (tmp_path / "README.md").write_text("# Hello\nWorld\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, env=env)
    return tmp_path


def test_cli_basic_run(git_repo):
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo)])
    assert result.exit_code == 0
    assert "Codebase Context" in result.output
    assert "main.py" in result.output


def test_cli_output_to_file(git_repo, tmp_path):
    out_file = tmp_path / "ctx.md"
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo), "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "Codebase Context" in content


def test_cli_budget_flag(git_repo):
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo), "--budget", "1000"])
    assert result.exit_code == 0


def test_cli_stats_flag(git_repo):
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo), "--stats"])
    assert result.exit_code == 0
    assert "allocation stats" in result.output


def test_cli_no_tests_flag(git_repo):
    (git_repo / "test_foo.py").write_text("def test_x(): pass\n")
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo), "--no-tests"])
    assert result.exit_code == 0
    assert "test_foo.py" not in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


def test_cli_empty_repo(tmp_path):
    """Non-git directory without commits should not crash."""
    runner = CliRunner()
    result = runner.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0


def test_cli_format_xml(git_repo):
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo), "--format", "xml"])
    assert result.exit_code == 0
    assert "<?xml" in result.output
    assert "<codebase_context" in result.output
    assert "<documents>" in result.output


def test_cli_format_markdown_default(git_repo):
    runner = CliRunner()
    result = runner.invoke(main, [str(git_repo)])
    assert result.exit_code == 0
    assert "# Codebase Context" in result.output
    assert "<?xml" not in result.output


def test_cli_clipboard_success(git_repo):
    runner = CliRunner()
    with patch("gitbrief.cli._copy_to_clipboard", return_value=True) as mock_clip:
        result = runner.invoke(main, [str(git_repo), "--clipboard"])
    assert result.exit_code == 0
    assert mock_clip.called
    assert "Copied to clipboard" in result.output


def test_cli_clipboard_failure(git_repo):
    runner = CliRunner()
    with patch("gitbrief.cli._copy_to_clipboard", return_value=False):
        result = runner.invoke(main, [str(git_repo), "--clipboard"])
    assert result.exit_code == 0
    # Falls back to stdout output
    assert "Codebase Context" in result.output


def test_copy_to_clipboard_macos():
    """Test macOS clipboard path with mocked subprocess."""
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            result = _copy_to_clipboard("hello")
    assert result is True
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["pbcopy"]


def test_copy_to_clipboard_unsupported_platform():
    with patch("sys.platform", "freebsd"):
        result = _copy_to_clipboard("hello")
    assert result is False
