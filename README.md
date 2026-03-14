# gitbrief

> Generate LLM-ready context from any git repository — in seconds.

```bash
gitbrief . --budget 8000 --clipboard              # copy to clipboard, ready to paste into Claude/GPT
gitbrief . --format xml                           # Claude-optimized XML output
gitbrief . --tree --prompt "Review for security"  # add directory tree + custom instruction
gitbrief . --changed-only --clipboard             # PR review: only files changed vs main
gitbrief . --changed-only --include-diff          # full PR context: diff + changed file contents
gitbrief-mcp                                      # start as MCP server (Claude Desktop integration)
```

[![PyPI version](https://img.shields.io/pypi/v/gitbrief.svg)](https://pypi.org/project/gitbrief/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-84%20passing-brightgreen.svg)](https://github.com/faw21/gitbrief)
[![MCP](https://img.shields.io/badge/MCP-server-purple.svg)](https://github.com/faw21/gitbrief)

---

## The problem

Every developer using LLMs (Claude, GPT, Gemini) manually copies code into chat windows.
You paste some files, forget others, include outdated versions, blow the context window, and guess at what's relevant.

**This is wasted engineering time.**

## The solution

`gitbrief` reads your **git history** to understand what's *actually important right now*, then packs the right files into a token-budget-aware document — perfect for pasting into any LLM.

```
$ gitbrief . --budget 8000 --stats

╭────────────────────────────╮
│ gitbrief allocation stats │
╰────────────────────────────╯
Token budget: 8,000 | Used: 7,999 (100%)
Files included: 6   | Skipped (budget): 194
Git commits analyzed: 100 | Branch: main

Top files by priority:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
┃ File                      ┃ Priority ┃ Tokens ┃ Changed? ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
│ src/auth/middleware.py    │     0.95 │    432 │ 🔥       │
│ src/auth/tokens.py        │     0.91 │    318 │ 🔥       │
│ README.md                 │     0.83 │  1,240 │ 🔥       │
│ pyproject.toml            │     0.75 │    168 │ —        │
└───────────────────────────┴──────────┴────────┴──────────┘
```

Files marked 🔥 were modified in recent commits. **The most relevant context surfaces automatically.**

---

## Why gitbrief beats alternatives

| Feature | gitbrief | repomix | llm-ctx | manual |
|---------|-----------|---------|---------|--------|
| Git-history-aware ranking | ✅ | ❌ | ❌ | ❌ |
| Token budget control | ✅ | ❌ | partial | ❌ |
| Recency decay scoring | ✅ | ❌ | ❌ | ❌ |
| Recent commits narrative | ✅ | ❌ | ❌ | ❌ |
| PR review mode (changed files only) | ✅ | ❌ | ❌ | ❌ |
| Include git diff in output | ✅ | ❌ | ❌ | ❌ |
| Single command | ✅ | ✅ | ✅ | ❌ |
| `--clipboard` flag | ✅ | ❌ | ❌ | ❌ |
| XML output (Claude-optimized) | ✅ | ❌ | ❌ | ❌ |
| Directory tree in output | ✅ | ✅ | ❌ | ❌ |
| Append custom instruction | ✅ | ❌ | ❌ | ❌ |
| **MCP server (Claude Desktop)** | ✅ | ❌ | ❌ | ❌ |

---

## Install

```bash
pip install gitbrief
```

For MCP server support (Claude Desktop integration):

```bash
pip install "gitbrief[mcp]"
```

Requires Python 3.10+ and optionally a git repository.

---

## Usage

```bash
# Basics
gitbrief .                          # current repo, 32k token budget
gitbrief /path/to/repo              # any repo

# Token budget control
gitbrief . --budget 8000            # fits GPT-4 32k
gitbrief . --budget 128000          # Claude 3.5 / GPT-4o full context

# Output
gitbrief . -o context.md            # write to file
gitbrief . --clipboard              # copy to clipboard (macOS/Linux/Windows)
gitbrief . | pbcopy                 # macOS: pipe to clipboard

# Format
gitbrief . --format xml             # Claude-optimized XML output (uses <documents> structure)
gitbrief . --format markdown        # default markdown output

# Filter
gitbrief . --no-tests               # skip test files (save tokens)

# PR review mode (v0.4+)
gitbrief . --changed-only                        # only files changed vs base branch (auto-detected)
gitbrief . --changed-only --base develop         # diff against a specific branch
gitbrief . --include-diff                        # add git diff to output
gitbrief . --changed-only --include-diff --clipboard  # ultimate PR review context

# Add context for LLM
gitbrief . --tree                   # include ASCII directory tree
gitbrief . --prompt "Review for security vulnerabilities"  # append instruction to context
gitbrief . --tree --prompt "What tests are missing?" --clipboard  # combine everything

# Debug
gitbrief . --stats                  # print allocation table to stderr
gitbrief . --max-commits 200        # analyze more git history
```

---

## Claude Desktop Integration (MCP)

`gitbrief` v0.5.0 ships as an **MCP server**, letting you use it directly inside Claude Desktop — no terminal switching needed.

### Setup

**1. Install with MCP support:**

```bash
pip install "gitbrief[mcp]"
```

**2. Add to Claude Desktop config:**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "gitbrief": {
      "command": "gitbrief-mcp"
    }
  }
}
```

**3. Restart Claude Desktop** — you'll see gitbrief tools in the toolbar.

### MCP tools exposed

| Tool | Description |
|------|-------------|
| `pack_context` | Pack repo into LLM-ready context (the main gitbrief command) |
| `get_repo_summary` | Get recent commits, hotspot files, and contributors |
| `list_repo_files` | List files ranked by git-history priority |

### Example prompts in Claude Desktop

Once configured, you can say things like:

- *"Pack my repo at ~/projects/myapp with an 8k token budget"*
- *"Show me what files changed most in ~/projects/api recently"*
- *"Pack only the changed files in my current branch for PR review"*

---

## How ranking works

`gitbrief` assigns each file a **priority score (0–1)**:

- **Recency** (60%): exponential decay — files changed today = 1.0, untouched 6 months = ~0.25
- **Frequency** (40%): normalized commit frequency across history
- **Recency bonus**: +0.2 if the file appeared in the most recent 20% of commits
- **Type bonuses**: README (+0.1), config files (+0.15)

Files are sorted by priority and greedily selected within your token budget.

---

## Development

```bash
git clone https://github.com/faw21/gitbrief
cd gitbrief
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/   # 84 tests, 90% coverage
```

---

## Related Tools

**[standup-ai](https://github.com/faw21/standup-ai)** — Generate your daily standup from git history using AI.

**[gpr](https://github.com/faw21/gpr)** — AI-powered PR descriptions and commit messages from your git diff.

**[critiq](https://github.com/faw21/critiq)** — AI code reviewer that runs locally before you push. Catches bugs and security issues with CRITICAL/WARNING severity levels.

**[changelog-ai](https://github.com/faw21/changelog-ai)** — Generate CHANGELOG entries from git history using AI.

**[git-chronicle](https://github.com/faw21/chronicle)** — AI-powered git history narrator. Turns your git log into engaging stories (narrative, timeline, or detective mode).

```bash
# The full AI-powered git workflow:
standup-ai --yesterday                                    # 1. morning standup
critiq                                                    # 2. AI review before committing
gpr --commit-run                                          # 3. commit with AI message
gitbrief . --changed-only --clipboard                    # 4. pack context for PR review
gpr                                                       # 5. generate PR description
changelog-ai --release-version v1.x.0 --prepend CHANGELOG.md  # 6. update changelog
chronicle file src/payments.py --style detective          # 7. understand complex history
```

---

## License

MIT
