"""gitbrief MCP server — exposes gitbrief functionality as MCP tools.

Allows LLM hosts like Claude Desktop to pack codebase context directly
without leaving the chat interface.

Usage:
    gitbrief-mcp              # start stdio MCP server (for Claude Desktop)
    python -m gitbrief.mcp_server  # alternative

Claude Desktop config (~/Library/Application Support/Claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "gitbrief": {
          "command": "gitbrief-mcp"
        }
      }
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .file_collector import collect_files
from .git_analyzer import analyze_repo, get_changed_files, get_diff
from .renderer import render_context
from .token_budget import fit_files_to_budget

mcp = FastMCP(
    "gitbrief",
    instructions=(
        "gitbrief packs your git repository into an LLM-ready context document. "
        "It uses git history to prioritize recently-changed files and fits the result "
        "within a token budget. Use pack_context to generate context for code review, "
        "debugging, or general LLM assistance."
    ),
)


def _detect_repo_root(path: Path) -> Path:
    """Walk up to find a .git directory."""
    current = path.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return path.resolve()


@mcp.tool()
def pack_context(
    path: str = ".",
    budget: int = 32000,
    fmt: str = "markdown",
    include_tree: bool = False,
    changed_only: bool = False,
    base: Optional[str] = None,
    include_diff: bool = False,
    prompt: Optional[str] = None,
    no_tests: bool = False,
    max_commits: int = 100,
    max_files: int = 200,
) -> str:
    """Pack a git repository into an LLM-ready context document.

    Analyzes git history to prioritize recently-changed files and fits the result
    within a token budget. Returns a markdown or XML document ready for LLM input.

    Args:
        path: Path to the git repository (default: current directory).
        budget: Token budget for the output (default: 32000). Increase for larger repos.
        fmt: Output format — 'markdown' (default) or 'xml' (Claude-optimized).
        include_tree: If True, prepend an ASCII directory tree of included files.
        changed_only: If True, only include files changed vs the base branch.
                      Useful for PR review context.
        base: Base branch for changed_only / include_diff (auto-detected if not set).
        include_diff: If True, include the full git diff in the output.
        prompt: Optional instruction to append (e.g. 'Review for security issues').
        no_tests: If True, exclude test files.
        max_commits: Number of recent commits to analyze for git signals (default: 100).
        max_files: Maximum files to consider before budget trimming (default: 200).

    Returns:
        A context document containing prioritized file contents, git summary,
        and optional directory tree / diff. Ready to paste into any LLM.
    """
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        return f"Error: path '{path}' does not exist."

    repo_root = _detect_repo_root(repo_path)

    try:
        file_scores, git_summary = analyze_repo(repo_root, max_commits=max_commits)
        ranked = collect_files(
            repo_root,
            file_scores,
            max_files=max_files,
            include_tests=not no_tests,
        )

        if changed_only:
            changed_paths = get_changed_files(repo_root, base_branch=base)
            if changed_paths:
                ranked = [f for f in ranked if f.relative_path in changed_paths]

        diff_content: Optional[str] = None
        if include_diff:
            diff_content = get_diff(repo_root, base_branch=base)

        selected, allocation = fit_files_to_budget(ranked, budget)
        document = render_context(
            repo_root,
            selected,
            git_summary,
            allocation,
            fmt=fmt,
            include_tree=include_tree,
            prompt=prompt,
            diff=diff_content,
        )
        return document

    except Exception as e:
        return f"Error generating context: {e}"


@mcp.tool()
def get_repo_summary(
    path: str = ".",
    max_commits: int = 100,
) -> str:
    """Get a concise summary of a git repository's recent activity.

    Returns information about recent commits, hotspot files (most frequently changed),
    contributors, and the current branch.

    Args:
        path: Path to the git repository (default: current directory).
        max_commits: Number of recent commits to analyze (default: 100).

    Returns:
        A markdown-formatted summary of the repository's recent git activity.
    """
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        return f"Error: path '{path}' does not exist."

    repo_root = _detect_repo_root(repo_path)

    try:
        _, git_summary = analyze_repo(repo_root, max_commits=max_commits)

        lines = [
            f"# Repository Summary: {repo_root.name}",
            f"",
            f"**Branch**: {git_summary.branch}",
            f"**Commits analyzed**: {git_summary.total_commits_analyzed}",
            f"",
        ]

        if git_summary.recent_commits:
            lines.append("## Recent Commits")
            for commit in git_summary.recent_commits[:10]:
                lines.append(
                    f"- `{commit['sha']}` {commit['message']} "
                    f"({commit['author']}, {commit['date'][:10]})"
                )
            lines.append("")

        if git_summary.most_changed_files:
            lines.append("## Hotspot Files (most frequently changed)")
            for f in git_summary.most_changed_files[:10]:
                lines.append(f"- `{f}`")
            lines.append("")

        if git_summary.active_authors:
            lines.append("## Top Contributors")
            for name in git_summary.active_authors[:5]:
                lines.append(f"- {name}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting repo summary: {e}"


@mcp.tool()
def list_repo_files(
    path: str = ".",
    max_files: int = 50,
    changed_only: bool = False,
    base: Optional[str] = None,
    no_tests: bool = False,
) -> str:
    """List files in a git repository ranked by git-history priority.

    Files that were recently changed frequently are ranked higher.
    Useful for understanding which files are most active in a project.

    Args:
        path: Path to the git repository (default: current directory).
        max_files: Maximum number of files to return (default: 50).
        changed_only: If True, only show files changed vs the base branch.
        base: Base branch for changed_only (auto-detected if not set).
        no_tests: If True, exclude test files.

    Returns:
        A markdown table of files with their priority scores and change status.
    """
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        return f"Error: path '{path}' does not exist."

    repo_root = _detect_repo_root(repo_path)

    try:
        file_scores, _ = analyze_repo(repo_root, max_commits=100)
        ranked = collect_files(
            repo_root,
            file_scores,
            max_files=max_files,
            include_tests=not no_tests,
        )

        if changed_only:
            changed_paths = get_changed_files(repo_root, base_branch=base)
            if changed_paths:
                ranked = [f for f in ranked if f.relative_path in changed_paths]

        if not ranked:
            return "No files found matching the criteria."

        lines = [
            f"# Files in {repo_root.name}",
            "",
            "| File | Priority | Recently Changed |",
            "|------|----------|------------------|",
        ]
        for rf in ranked[:max_files]:
            changed_marker = "🔥 Yes" if rf.is_recently_changed else "No"
            lines.append(f"| `{rf.relative_path}` | {rf.priority:.3f} | {changed_marker} |")

        lines.append("")
        lines.append(f"*{len(ranked)} files listed*")
        return "\n".join(lines)

    except Exception as e:
        return f"Error listing files: {e}"


def run() -> None:
    """Entry point for gitbrief-mcp command."""
    mcp.run()


if __name__ == "__main__":
    run()
