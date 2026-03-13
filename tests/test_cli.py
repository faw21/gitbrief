"""Integration tests for the CLI."""

import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from gitbrief.cli import main


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
    assert "0.1.0" in result.output


def test_cli_empty_repo(tmp_path):
    """Non-git directory without commits should not crash."""
    runner = CliRunner()
    result = runner.invoke(main, [str(tmp_path)])
    assert result.exit_code == 0
