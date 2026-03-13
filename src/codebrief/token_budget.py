"""Token budget management and file selection within budget."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")  # GPT-4 / Claude compatible
    HAS_TIKTOKEN = True
except Exception:
    HAS_TIKTOKEN = False


def count_tokens(text: str) -> int:
    """Count tokens in text. Falls back to char/4 estimate."""
    if HAS_TIKTOKEN:
        return len(_ENC.encode(text))
    return max(1, len(text) // 4)


@dataclass
class BudgetAllocation:
    """How the token budget was split."""

    total_budget: int
    header_tokens: int
    git_summary_tokens: int
    files_tokens: int
    files_included: int
    files_skipped: int
    budget_used: int

    @property
    def utilization_pct(self) -> float:
        return 100.0 * self.budget_used / max(1, self.total_budget)


def fit_files_to_budget(
    ranked_files: list,  # list[RankedFile]
    budget: int,
    reserved_for_header: int = 500,
    reserved_for_git: int = 800,
) -> tuple[list, BudgetAllocation]:
    """
    Select as many high-priority files as possible within the token budget.

    Returns:
        (selected_files, allocation)
    """
    available = budget - reserved_for_header - reserved_for_git
    available = max(0, available)

    selected = []
    used = 0
    skipped = 0

    for rf in ranked_files:
        # Read actual content for accurate token count
        try:
            content = rf.path.read_text(encoding="utf-8", errors="replace")
            tokens = count_tokens(content)
        except Exception:
            skipped += 1
            continue

        # Leave at least 10% headroom for each subsequent file
        if used + tokens > available:
            skipped += 1
            continue

        selected.append((rf, content, tokens))
        used += tokens

    alloc = BudgetAllocation(
        total_budget=budget,
        header_tokens=reserved_for_header,
        git_summary_tokens=reserved_for_git,
        files_tokens=used,
        files_included=len(selected),
        files_skipped=skipped,
        budget_used=reserved_for_header + reserved_for_git + used,
    )
    return selected, alloc
