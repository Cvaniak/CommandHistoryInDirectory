<p align="center">
  <h1 align="center">🔍 Command History In Directory (CHID)</h1>
  <p align="center">
    <strong>Context-aware, directory-scoped command history, frequency ranking, and pipeline flag analysis for modern shells.</strong>
  </p>
</p>

---

## ⚡ Overview

When navigating between projects, developers frequently forget the exact build flags, deploy scripts, or testing commands used in that specific codebase months ago. Standard shell history mixes every directory together into one monolithic file.

**CHID** records every command you run directly into an ultra-fast, concurrent SQLite database, keeping track of:
- **Directory & Git Repository Context**
- **Execution Duration & Millisecond Precision**
- **Exit Status (`✔ 0` or `✘ Non-Zero`)**
- **Frequency Percentages & Recency**
- **Option Flag & Pipeline Decomposition** (`chid --flags <tool>`)
- **Interactive Command Buffer Replacement** (`Ctrl+Space`)

CHID supports **Zsh**, **Bash**, and **Fish** with near-zero latency (<0.2ms overhead), never slowing down your prompt.

---

## 🚀 Installation

### 1. Install the Python Package
Requires Python `>= 3.10`:
```bash
pip install .
```
Or for local development:
```bash
pip install -e ".[dev]"
```

### 2. Activate in Your Shell

#### **Zsh**
Add to your `~/.zshrc`:
```zsh
eval "$(chid init zsh)"
```

#### **Bash**
Add to your `~/.bashrc`:
```bash
eval "$(chid init bash)"
```

#### **Fish**
Add to your `~/.config/fish/config.fish`:
```fish
chid init fish | source
```

---

## 📖 CLI Usage

### View Frequent Commands (Default)
Displays the most frequently used commands in the current directory with percentage share and relative timestamps:
```bash
chid
```

### View Recent History with Status & Duration
Displays recent commands with execution duration badges and colored exit status indicators:
```bash
chid -r
```

### Git Repository-Wide Scope
Scope queries across the entire Git repository, regardless of what subdirectory you are currently in:
```bash
chid -R
chid -r -R
```

### Substring Search & Exit Status Filters
```bash
# Search for commands matching 'docker'
chid -s docker

# Show only successful commands
chid --success

# Show only failed commands
chid --failed
```

### Pipeline Decomposition & Flag Analysis
Analyze flag usage, option percentages, and common invocation patterns for any tool across compound pipelines (`&&`, `||`, `|`, `;`):
```bash
# Analyze all flags used with 'git'
chid --flags git

# Analyze flags specifically for 'git commit'
chid --flags git commit
```

### Clear Current Directory History
```bash
chid --clear
```

### Time-Based History Filtering
Filter command history by relative durations, preset periods, or date ranges:
```bash
# Commands executed in the last 30 minutes
chid -r --last 30m

# Commands executed today or yesterday
chid --today
chid -r --yesterday

# Commands executed after/since a specific time (relative duration, date, or time of day)
chid --since 2h
chid --after 2026-09-01

# Commands executed before/until a specific time
chid --until 1d
chid --before 18:00

# Commands within a specific time window (start..end)
chid --range 2h..30m
chid -r --range 2026-09-01..2026-09-05
```

---

## ⌨️ Interactive Buffer Replacement

Instead of retyping long commands, CHID lets you recall any displayed command into your terminal buffer:

1. Run `chid` or `chid -r` to view commands with index numbers (`1`, `2`, `3`...).
2. Type `chid <index>` (e.g. `chid 2`).
3. Press **`Ctrl+Space`** (or **`Ctrl+@`**).
4. The buffer instantly replaces `chid 2` with the exact original command line, ready to edit or run!

---

## 🛠️ CLI Options Reference

| Flag | Description |
| :--- | :--- |
| `-f`, `--freq` | Sort history by frequency of execution (default). |
| `-r`, `--recent` | Sort history by recency (most recent execution first). |
| `--first` | Sort history chronologically (earliest execution first). |
| `-R`, `--repo` | Scope query to the current Git repository root. |
| `-n`, `-l`, `--limit <N>` | Limit the number of displayed records (default: 20). |
| `-s`, `-q`, `--search <STR>` | Filter records matching keyword substring. |
| `-a`, `--all` | Include all commands, including typos and bad parameters (filtered out by default). |
| `--invalid`, `--bad` | Display only commands that were incorrect (e.g. typos, command not found) or had invalid parameters. |
| `-F`, `--flags <TOOL> [SUBCMD]` | Analyze flag and option frequencies for tool. |
| `--success` | Show only commands that exited with code 0. |
| `--failed` | Show only commands that exited with non-zero exit code. |
| `--since`, `--after <TIME>` | Show commands executed after given time (e.g. `30m`, `2h`, `1d`, `YYYY-MM-DD`, `HH:MM`). |
| `--until`, `--before <TIME>` | Show commands executed before given time. |
| `--last <DURATION>` | Show commands from the last duration (e.g. `15m`, `2h`, `1d`). |
| `--today` | Show commands executed today. |
| `--yesterday` | Show commands executed yesterday. |
| `--range <START..END>` | Show commands within a time range (e.g. `2h..30m` or `2026-09-01..2026-09-05`). |
| `--raw` | Output unformatted command lines (one per line, ideal for scripting). |
| `--clear` | Delete all history records for the current directory. |
| `--version` | Display CHID version information. |

---

## ⚙️ Environment Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `CHID_SESSION` | `$$` (Shell PID) | Session identifier used for per-terminal buffer isolation. |
| `CHID_ALIAS` | `""` | Optional shell alias (e.g. `h`) tracked for replacement and ignored from history. |
| `CHID_SHORTCUT` | `^ ` (`Ctrl+Space`) | Custom Zsh keybinding for buffer replacement. |
| `CHID_DB_PATH` | `~/.local/share/chid/history.sqlite` | Custom SQLite database file location. |

---

## 🧪 Testing

Run the automated test suite:
```bash
python3 -m unittest discover -s tests -v
```

---

## 📄 License

MIT License. Copyright (c) 2026 Cvaniak.
