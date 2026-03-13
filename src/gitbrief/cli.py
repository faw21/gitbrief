"""gitbrief CLI entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .file_collector import collect_files
from .git_analyzer import analyze_repo, get_changed_files, get_diff
from .renderer import render_context
from .token_budget import fit_files_to_budget

console = Console(stderr=True)  # progress to stderr, output to stdout


def _detect_repo_root(path: Path) -> Path:
    """Walk up to find a .git directory."""
    current = path.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return path.resolve()


@click.command(name="gitbrief")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--budget", "-b",
    default=32000,
    show_default=True,
    help="Token budget for the output context.",
)
@click.option(
    "--output", "-o",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help="Write output to file instead of stdout.",
)
@click.option(
    "--no-tests",
    is_flag=True,
    default=False,
    help="Exclude test files.",
)
@click.option(
    "--max-commits",
    default=100,
    show_default=True,
    help="Number of recent commits to analyze for git signals.",
)
@click.option(
    "--max-files",
    default=200,
    show_default=True,
    help="Maximum files to consider before budget trimming.",
)
@click.option(
    "--stats",
    is_flag=True,
    default=False,
    help="Print allocation stats to stderr.",
)
@click.option(
    "--format", "-f",
    "fmt",
    type=click.Choice(["markdown", "xml"], case_sensitive=False),
    default="markdown",
    show_default=True,
    help="Output format. 'xml' is optimized for Claude's context window.",
)
@click.option(
    "--clipboard", "-c",
    is_flag=True,
    default=False,
    help="Copy output to clipboard (macOS/Linux/Windows).",
)
@click.option(
    "--tree",
    is_flag=True,
    default=False,
    help="Include an ASCII directory tree of included files.",
)
@click.option(
    "--prompt", "-p",
    "user_prompt",
    default=None,
    metavar="TEXT",
    help="Append a custom instruction to the context (e.g. 'Review for security issues').",
)
@click.option(
    "--changed-only",
    is_flag=True,
    default=False,
    help="Only include files changed vs base branch (auto-detected). Perfect for PR review context.",
)
@click.option(
    "--base",
    default=None,
    help="Base branch for --changed-only and --include-diff (auto-detected if not set).",
)
@click.option(
    "--include-diff",
    is_flag=True,
    default=False,
    help="Include git diff in the output (useful for code review).",
)
@click.version_option(__version__, prog_name="gitbrief")
def main(
    path: str,
    budget: int,
    output: Optional[str],
    no_tests: bool,
    max_commits: int,
    max_files: int,
    stats: bool,
    fmt: str,
    clipboard: bool,
    tree: bool,
    user_prompt: Optional[str],
    changed_only: bool,
    base: Optional[str],
    include_diff: bool,
) -> None:
    """Generate an LLM-ready context document from a git repository.

    Analyzes git history to prioritize recently-changed files and fits
    the result within a token budget you control.

    \b
    Examples:
      gitbrief .                                        # current dir, 32k tokens
      gitbrief . --budget 8000                          # tight budget for small context
      gitbrief /path/to/repo -o ctx.md                  # write to file
      gitbrief . --no-tests --stats                     # skip tests, show allocation
      gitbrief . --clipboard                            # copy to clipboard (any platform)
      gitbrief . --format xml                           # Claude-optimized XML output
      gitbrief . --tree                                 # include directory structure
      gitbrief . -p "Review this for security issues"   # append instruction
      gitbrief . --changed-only --clipboard             # PR review: only changed files
      gitbrief . --changed-only --include-diff          # full PR context: diff + changed files
      gitbrief . | pbcopy                               # copy to clipboard (macOS pipe)
    """
    repo_path = Path(path).resolve()
    repo_root = _detect_repo_root(repo_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        t1 = progress.add_task("Analyzing git history…", total=None)
        file_scores, git_summary = analyze_repo(repo_root, max_commits=max_commits)
        progress.update(t1, completed=True)

        t2 = progress.add_task("Collecting & ranking files…", total=None)
        ranked = collect_files(
            repo_root,
            file_scores,
            max_files=max_files,
            include_tests=not no_tests,
        )
        progress.update(t2, completed=True)

        # Filter to changed-only files if requested
        if changed_only:
            progress.add_task("Filtering to changed files…", total=None)
            changed_paths = get_changed_files(repo_root, base_branch=base)
            if changed_paths:
                ranked = [f for f in ranked if f.relative_path in changed_paths]
                if not ranked:
                    console.print("[yellow]⚠[/yellow] No changed files found vs base branch. "
                                  "Use --base to specify a different base, or omit --changed-only.")

        # Get diff if requested
        diff_content: Optional[str] = None
        if include_diff:
            progress.add_task("Getting git diff…", total=None)
            diff_content = get_diff(repo_root, base_branch=base)

        t3 = progress.add_task(f"Fitting {len(ranked)} files into {budget:,} token budget…", total=None)
        selected, allocation = fit_files_to_budget(ranked, budget)
        progress.update(t3, completed=True)

        t4 = progress.add_task("Rendering context document…", total=None)
        document = render_context(
            repo_root,
            selected,
            git_summary,
            allocation,
            fmt=fmt,
            include_tree=tree,
            prompt=user_prompt,
            diff=diff_content,
        )
        progress.update(t4, completed=True)

    if stats:
        _print_stats(git_summary, allocation, selected, console)

    if clipboard:
        success = _copy_to_clipboard(document)
        if success:
            console.print(
                f"[green]✓[/green] Copied to clipboard "
                f"([bold]{allocation.budget_used:,}[/bold] tokens, "
                f"[bold]{allocation.files_included}[/bold] files)"
            )
        else:
            console.print("[yellow]⚠[/yellow] Clipboard copy failed — "
                          "install xclip/xsel on Linux, or use pbcopy on macOS.")
            click.echo(document)
    elif output:
        out_path = Path(output)
        out_path.write_text(document, encoding="utf-8")
        console.print(f"[green]✓[/green] Written to [bold]{out_path}[/bold] "
                      f"({allocation.budget_used:,} tokens)")
    else:
        # Raw output to stdout for piping
        click.echo(document)


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return True
        if sys.platform.startswith("linux"):
            for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                try:
                    subprocess.run(cmd, input=text.encode(), check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16"), check=True)
            return True
    except Exception:
        pass
    return False


def _print_stats(git_summary, allocation, selected, c: Console) -> None:
    """Print a rich stats table to stderr."""
    c.print()
    c.print(Panel.fit("[bold cyan]gitbrief allocation stats[/bold cyan]"))

    tbl = Table(show_header=True, header_style="bold")
    tbl.add_column("Metric", style="dim")
    tbl.add_column("Value", justify="right")

    tbl.add_row("Token budget", f"{allocation.total_budget:,}")
    tbl.add_row("Tokens used", f"{allocation.budget_used:,}")
    tbl.add_row("Utilization", f"{allocation.utilization_pct:.1f}%")
    tbl.add_row("Files included", str(allocation.files_included))
    tbl.add_row("Files skipped (budget)", str(allocation.files_skipped))
    tbl.add_row("Git commits analyzed", str(git_summary.total_commits_analyzed))
    tbl.add_row("Branch", git_summary.branch)
    c.print(tbl)

    if selected:
        c.print("\n[bold]Top files by priority:[/bold]")
        top_tbl = Table(show_header=True, header_style="bold")
        top_tbl.add_column("File")
        top_tbl.add_column("Priority", justify="right")
        top_tbl.add_column("Tokens", justify="right")
        top_tbl.add_column("Changed?")
        for rf, _content, tokens in selected[:10]:
            top_tbl.add_row(
                rf.relative_path,
                f"{rf.priority:.2f}",
                f"{tokens:,}",
                "🔥" if rf.is_recently_changed else "—",
            )
        c.print(top_tbl)
    c.print()
