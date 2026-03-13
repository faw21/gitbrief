# gitbrief

> Generate LLM-ready context from any git repository — in seconds.

```bash
gitbrief . --budget 8000 | pbcopy   # copy to clipboard, ready to paste into Claude/GPT
```

[![PyPI version](https://img.shields.io/pypi/v/gitbrief.svg)](https://pypi.org/project/gitbrief/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-38%20passing-brightgreen.svg)](https://github.com/faw21/gitbrief)

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
| Single command | ✅ | ✅ | ✅ | ❌ |

---

## Install

```bash
pip install gitbrief
```

> **Note**: PyPI release coming soon. Until then, install from source:
> ```bash
> pip install git+https://github.com/faw21/gitbrief.git
> ```

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
gitbrief . | pbcopy                 # macOS: copy to clipboard
gitbrief . | xclip -selection clipboard  # Linux

# Filter
gitbrief . --no-tests               # skip test files (save tokens)

# Debug  
gitbrief . --stats                  # print allocation table to stderr
gitbrief . --max-commits 200        # analyze more git history
```

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
pytest tests/   # 38 tests, 93% coverage
```

---

## License

MIT
