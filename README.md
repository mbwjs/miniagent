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

## Why MiniAgent?

> **不丢记忆 + 极低成本 + 单文件 800 行 = 一个真正能跑长任务的 VPS agent。**

| 优点 | 说明 |
|---|---|
| 🧠 **LLM 压缩上下文** | 不是滑动窗口丢消息。超 60k token 时，调用 API 自动把旧消息摘要成 bullet points，保留全部语义不丢失关键决策。 |
| 📝 **双文件记忆系统** | `AGENT.md` = 行为指令，`MEMORY.md` = 跨会话持久记忆。随时编辑控制 agent 行为，无需改代码。 |
| 💰 **极低成本** | 默认 `deepseek-v4-pro`（$0.14/M input），一次压缩只需几分钱。模型可切换，每轮精确计费。 |
| 🧩 **单文件，零框架** | 仅 800 行 Python，直接调 Anthropic API tool_use，无 LangChain/AutoGPT 等重型依赖。 |
| 🚀 **一键发博客** | `publish_post` 工具自动生成 Hugo frontmatter → 构建 → rsync 部署到 nginx，全链路自动化。 |
| 🔒 **安全硬拦截** | `rm -rf /`、`sudo`、`shutdown` 等危险命令直接拒绝，文件路径限定在工作目录，bash 30s 超时。 |
| 👁️ **工具执行透明** | 每个工具调用实时显示 icon + 输入参数 + 输出预览，全程可见不黑盒。 |
| 🛠️ **运维友好** | `/stable` 一键 git tag、`/restore` 回滚、`/nohistory` 无上下文模式、`/context` 全貌诊断。 |

## Architecture

- **ReAct loop**: Agent receives a query → decides which tools to call → executes tools → feeds results back → loops until done
- **Context compression**: When >60k estimated tokens, old messages are LLM-summarized into bullet points (not dropped). Keeps first anchor + compressed summary + last 24 messages intact.
- **Cost tracking**: Per-turn and per-session token counting with pricing by model
- **Logging**: Rotating log at `agent.log` (5MB × 5 backups)

## Safety

- Commands like `rm -rf /`, `sudo`, `shutdown`, `reboot`, `mkfs` are blocked
- All file paths resolved relative to `WORKDIR`
- Bash commands get a 30-second timeout
