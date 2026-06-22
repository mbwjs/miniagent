# 🧠 MiniAgent

ReAct agent for VPS — coding, web search, blog publishing, all from a CLI.

> **No memory loss + ultra-low cost + single 800-line file = a VPS agent that actually handles long-running tasks.**

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
| `/compress` | Manually trigger context compression |
| `/stable` | Git commit + tag current `agent.py` as "stable" |
| `/restore` | Checkout `agent.py` from the "stable" tag (restart required) |
| `/memory` | Show MEMORY.md contents |
| `/context` | Context overview (tokens, cost, compression, files) |
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

## Why MiniAgent?

| Advantage | Description |
|---|---|
| 🧠 **LLM Context Compression** | Not a sliding window that drops messages. When >60k tokens, auto-calls API to summarize old messages into bullet points — all semantics preserved, no key decisions lost. |
| 📝 **Dual-File Memory** | `AGENT.md` = behavior instructions, `MEMORY.md` = persistent cross-session memory. Edit either to control agent behavior — no code changes needed. |
| 💰 **Ultra-Low Cost** | Defaults to `deepseek-v4-pro` ($0.14/M input, $1.10/M output). One compression call costs fractions of a cent. Model-switchable, per-turn billing. |
| 🧩 **Single File, Zero Frameworks** | Just 800 lines of Python. Direct Anthropic API tool_use calls. No LangChain, AutoGPT, or other heavy deps. |
| 🚀 **One-Click Blog Publishing** | `publish_post` auto-generates Hugo frontmatter → builds → rsync deploys to nginx. Full pipeline in one call. |
| 🔒 **Hard Safety Filter** | `rm -rf /`, `sudo`, `shutdown`, `reboot`, `mkfs` are blocked outright. File paths confined to WORKDIR. 30s bash timeout. |
| 👁️ **Transparent Tool Execution** | Every tool call shows icon + input params + output preview. Nothing is hidden. |
| 🛠️ **Ops-Friendly** | `/stable` one-click git tag, `/restore` rollback, `/nohistory` stateless mode, `/context` full diagnostic. |

## Architecture

- **ReAct loop**: Agent receives a query → decides which tools to call → executes tools → feeds results back → loops until done
- **Context compression**: When >60k estimated tokens, old messages are LLM-summarized into bullet points (not dropped). Keeps first anchor + compressed summary + last 24 messages intact.
- **Cost tracking**: Per-turn and per-session token counting with pricing by model
- **Logging**: Rotating log at `agent.log` (5MB × 5 backups)

## Safety

- Commands like `rm -rf /`, `sudo`, `shutdown`, `reboot`, `mkfs` are blocked
- All file paths resolved relative to `WORKDIR`
- Bash commands get a 30-second timeout
