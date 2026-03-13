"""Tests for file_collector module."""

import os
from pathlib import Path

import pytest

from gitbrief.file_collector import collect_files, _is_binary, _token_estimate


def make_file(tmp_path: Path, rel: str, content: str = "hello world") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_collect_empty_dir(tmp_path):
    files = collect_files(tmp_path, {})
    assert files == []


def test_collect_basic_files(tmp_path):
    make_file(tmp_path, "main.py", "x = 1")
    make_file(tmp_path, "README.md", "# Hello")
    files = collect_files(tmp_path, {})
    paths = [f.relative_path for f in files]
    assert "main.py" in paths
    assert "README.md" in paths


def test_collect_skips_hidden_dirs(tmp_path):
    make_file(tmp_path, ".git/config", "[core]")
    make_file(tmp_path, "main.py", "x = 1")
    files = collect_files(tmp_path, {})
    paths = [f.relative_path for f in files]
    assert all(".git" not in p for p in paths)


def test_collect_skips_pycache(tmp_path):
    make_file(tmp_path, "__pycache__/foo.cpython-311.pyc", "\x00binary")
    make_file(tmp_path, "main.py", "x = 1")
    files = collect_files(tmp_path, {})
    paths = [f.relative_path for f in files]
    assert all("__pycache__" not in p for p in paths)


def test_collect_skips_pyc_extension(tmp_path):
    make_file(tmp_path, "module.pyc", "\x00binary")
    make_file(tmp_path, "main.py", "x = 1")
    files = collect_files(tmp_path, {})
    paths = [f.relative_path for f in files]
    assert all(not p.endswith(".pyc") for p in paths)


def test_collect_excludes_tests_when_flagged(tmp_path):
    make_file(tmp_path, "main.py", "x = 1")
    make_file(tmp_path, "tests/test_main.py", "def test_x(): pass")
    files_with = collect_files(tmp_path, {}, include_tests=True)
    files_without = collect_files(tmp_path, {}, include_tests=False)
    with_paths = [f.relative_path for f in files_with]
    without_paths = [f.relative_path for f in files_without]
    assert any("test" in p for p in with_paths)
    assert not any("test" in p for p in without_paths)


def test_collect_readme_gets_higher_priority_than_plain_py(tmp_path):
    make_file(tmp_path, "README.md", "# Big readme\n" * 50)
    make_file(tmp_path, "helper.py", "# helper\n" * 50)
    files = collect_files(tmp_path, {})
    readme = next((f for f in files if "README" in f.relative_path), None)
    helper = next((f for f in files if "helper" in f.relative_path), None)
    assert readme is not None
    assert helper is not None
    assert readme.priority >= helper.priority


def test_is_binary_with_null_bytes(tmp_path):
    p = tmp_path / "bin.bin"
    p.write_bytes(b"\x00\x01\x02")
    assert _is_binary(p) is True


def test_is_binary_with_text(tmp_path):
    p = tmp_path / "text.txt"
    p.write_text("hello world")
    assert _is_binary(p) is False


def test_token_estimate_nonempty(tmp_path):
    p = tmp_path / "f.py"
    p.write_text("x = 1" * 100)
    tokens = _token_estimate(p)
    assert tokens > 0
