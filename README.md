# 🧠 MiniAgent

ReAct agent for VPS — coding, web search, blog publishing, all from a CLI.

## Setup

```bash
# 1. Set your API key
export ANTHROPIC_API_KEY="sk-..."

# 2. Optional: use a different provider/model
export ANTHROPIC_BASE_URL="https://api.deepseek.com"
export ANTHROPIC_MODEL="deepseek-v4-pro"

# 3. Install deps
pip3 install anthropic duckduckgo_search
```

## Usage

```bash
python3 agent.py
```

Type your query and the agent will use tools (bash, read, write, edit, glob, web_search, web_fetch, publish_post) in a ReAct loop to fulfill it.

## Built-in Commands

| Command | What it does |
|---|---|
| `/help` / `/h` | Show full help |
| `/clear` | Clear session history & token counters |
| `/system` | Show the system prompt and available tools |
| `/tokens` | Show current session token usage & cost |
| `/cost` | Show per-turn cost breakdown |
| `/nohistory` | Toggle: each query starts fresh (no context carried over) |
| `/stable` | Git commit + tag current `agent.py` as "stable" |
| `/restore` | Checkout `agent.py` from the "stable" tag (restart required) |
| `q` / `exit` / `quit` | Quit the agent |

## Tools Available to the Agent

- **bash** — Run shell commands (dangerous commands blocked, 30s timeout)
- **read** — Read file contents with line numbers
- **write** — Write/overwrite files (creates parent dirs)
- **edit** — Find-and-replace first occurrence in a file
- **glob** — Find files by pattern
- **web_search** — Search DuckDuckGo
- **web_fetch** — Fetch and extract text from a URL
- **publish_post** — Create a Hugo blog post, build, and rsync deploy to `aipulse.lol`

## Blog Publishing

Requires Hugo installed and these paths configured in `agent.py`:

- `BLOG_DIR = ~/aipulse` (Hugo site root)
- `BLOG_DEPLOY = /var/www/aitracker` (nginx document root)

The agent auto-generates frontmatter, runs `hugo --buildFuture`, and rsyncs to the deploy path.

## Architecture

- **ReAct loop**: Agent receives a query → decides which tools to call → executes tools → feeds results back → loops until done
- **Sliding window**: Keeps first anchor message + last 30 messages (preserves tool_use/tool_result pairs)
- **Cost tracking**: Per-turn and per-session token counting with pricing by model
- **Logging**: Rotating log at `agent.log` (5MB × 5 backups)

## Safety

- Commands like `rm -rf /`, `sudo`, `shutdown`, `reboot`, `mkfs` are blocked
- All file paths resolved relative to `WORKDIR`
- Bash commands get a 30-second timeout
