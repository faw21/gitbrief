"""Tests for token_budget module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codebrief.token_budget import count_tokens, fit_files_to_budget


def test_count_tokens_nonempty():
    tokens = count_tokens("hello world")
    assert tokens > 0


def test_count_tokens_empty():
    tokens = count_tokens("")
    assert tokens == 0 or tokens == 1  # tiktoken may give 0, fallback gives 1


def test_count_tokens_proportional():
    short = count_tokens("hi")
    long = count_tokens("hi " * 100)
    assert long > short


def _make_ranked_file(tmp_path: Path, name: str, content: str):
    """Create a mock RankedFile pointing to a real file."""
    p = tmp_path / name
    p.write_text(content)
    rf = MagicMock()
    rf.path = p
    rf.relative_path = name
    rf.is_recently_changed = False
    rf.priority = 0.5
    rf.git_change_count = 1
    return rf


def test_fit_files_empty_list():
    selected, alloc = fit_files_to_budget([], budget=8000)
    assert selected == []
    assert alloc.files_included == 0
    assert alloc.files_skipped == 0


def test_fit_files_within_budget(tmp_path):
    rf1 = _make_ranked_file(tmp_path, "a.py", "x = 1\n" * 10)
    rf2 = _make_ranked_file(tmp_path, "b.py", "y = 2\n" * 10)
    selected, alloc = fit_files_to_budget([rf1, rf2], budget=10000)
    assert len(selected) == 2
    assert alloc.files_included == 2
    assert alloc.files_skipped == 0


def test_fit_files_exceeds_budget(tmp_path):
    # Large content that exceeds budget
    rf1 = _make_ranked_file(tmp_path, "big.py", "x = 1\n" * 5000)
    rf2 = _make_ranked_file(tmp_path, "small.py", "y = 2\n")
    # Small budget
    selected, alloc = fit_files_to_budget([rf1, rf2], budget=300)
    # big.py should be skipped (too many tokens), small.py might fit
    assert alloc.files_skipped >= 1


def test_fit_budget_allocation_totals(tmp_path):
    rf = _make_ranked_file(tmp_path, "f.py", "x = 1\n" * 50)
    selected, alloc = fit_files_to_budget([rf], budget=8000)
    assert alloc.total_budget == 8000
    assert alloc.budget_used <= alloc.total_budget
    assert alloc.utilization_pct <= 100.0
