"""codebrief CLI entry point."""

from __future__ import annotations

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
from .git_analyzer import analyze_repo
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


@click.command(name="codebrief")
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
@click.version_option(__version__, prog_name="codebrief")
def main(
    path: str,
    budget: int,
    output: Optional[str],
    no_tests: bool,
    max_commits: int,
    max_files: int,
    stats: bool,
) -> None:
    """Generate an LLM-ready context document from a git repository.

    Analyzes git history to prioritize recently-changed files and fits
    the result within a token budget you control.

    \b
    Examples:
      codebrief .                          # current dir, 32k tokens
      codebrief . --budget 8000            # tight budget for small context
      codebrief /path/to/repo -o ctx.md    # write to file
      codebrief . --no-tests --stats       # skip tests, show allocation
      codebrief . | pbcopy                 # copy to clipboard (macOS)
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

        t3 = progress.add_task(f"Fitting {len(ranked)} files into {budget:,} token budget…", total=None)
        selected, allocation = fit_files_to_budget(ranked, budget)
        progress.update(t3, completed=True)

        t4 = progress.add_task("Rendering context document…", total=None)
        document = render_context(repo_root, selected, git_summary, allocation)
        progress.update(t4, completed=True)

    if stats:
        _print_stats(git_summary, allocation, selected, console)

    if output:
        out_path = Path(output)
        out_path.write_text(document, encoding="utf-8")
        console.print(f"[green]✓[/green] Written to [bold]{out_path}[/bold] "
                      f"({allocation.budget_used:,} tokens)")
    else:
        # Raw output to stdout for piping
        click.echo(document)


def _print_stats(git_summary, allocation, selected, c: Console) -> None:
    """Print a rich stats table to stderr."""
    c.print()
    c.print(Panel.fit("[bold cyan]codebrief allocation stats[/bold cyan]"))

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
