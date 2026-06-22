#!/usr/bin/env python3
"""
MiniAgent — ReAct agent for VPS
  coding tools (bash/read/write/edit/glob) + web_search + web_fetch + publish_post
  sliding window context management

Usage: python3 agent_vps.py
"""
from __future__ import annotations
import os, sys, subprocess, json, re, urllib.request, urllib.parse, inspect, logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone, timedelta

from anthropic import Anthropic

# ── Logging ─────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = LOG_DIR / "agent.log"

logger = logging.getLogger("miniagent")
logger.setLevel(logging.DEBUG)

# Rotating: 5MB per file, keep 5 backups
fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname).1s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(fh)

# ── Config ──────────────────────────────────────────────
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL    = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro")

if not API_KEY:
    print("❌ ANTHROPIC_API_KEY not set")
    sys.exit(1)

if "deepseek" in BASE_URL:
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

client = Anthropic(base_url=BASE_URL, api_key=API_KEY)
WORKDIR = Path.cwd()
CST = timezone(timedelta(hours=8))

# Blog config (VPS paths)
BLOG_DIR = Path.home() / "aipulse"
BLOG_DEPLOY = "/var/www/aitracker"
BLOG_URL = "https://aipulse.lol"

# ── Pricing ─────────────────────────────────────────────
PRICING = {
    "deepseek-v4-pro":   {"input": 0.14, "output": 1.10},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
}

def calc_cost(model: str, in_tok: int, out_tok: int) -> float | None:
    p = PRICING.get(model)
    return (in_tok * p["input"] + out_tok * p["output"]) / 1_000_000 if p else None

# ── Colors ──────────────────────────────────────────────
C = {"cyan":"\033[36m","green":"\033[32m","yellow":"\033[33m","red":"\033[31m",
     "dim":"\033[90m","reset":"\033[0m","bold":"\033[1m"}

# ── System Prompt ───────────────────────────────────────
AGENT_INSTRUCT = ""
AGENT_MD = WORKDIR / "agent.md"
if AGENT_MD.exists():
    AGENT_INSTRUCT = AGENT_MD.read_text(encoding="utf-8")

MEMORY_MD = WORKDIR / "AGENT.md"
AGENT_MEMORY = ""
if MEMORY_MD.exists():
    AGENT_MEMORY = MEMORY_MD.read_text(encoding="utf-8")
    lines = AGENT_MEMORY.splitlines()
    if len(lines) > 200:
        AGENT_MEMORY = "\n".join(lines[-200:])
        logger.warning("AGENT.md >200 lines, truncated to last 200")

SYSTEM = f"""You are a coding + writing agent on a VPS (AlmaLinux 9, {WORKDIR}).
Use tools proactively. Write code, search the web, publish blog posts.

Rules:
- Act directly, don't explain before doing.
- Read files before editing them.
- For blog posts: use publish_post tool — it handles frontmatter + build + deploy.
- Search the web before writing about current events.
- Keep responses short — the user sees tool outputs.
- Blog posts at {BLOG_URL}

── Agent Instructions ({WORKDIR}/agent.md) ──
{AGENT_INSTRUCT}
── End Instructions ──

── Persistent Memory ({WORKDIR}/AGENT.md) ──
{AGENT_MEMORY}
── End Memory ──"""

# ── Tool Definitions ────────────────────────────────────
TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command. Returns stdout+stderr (first 10k chars).",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read",
        "description": "Read file contents with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer", "description": "Max lines (optional)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write",
        "description": "Write/overwrite a file. Creates parent dirs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit",
        "description": "Replace first occurrence of old_text with new_text in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern (**/*.py, *.go, etc).",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web via DuckDuckGo. Returns title, snippet, URL for each result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results, default 5"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch a URL and return extracted text content (first 5000 chars).",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "publish_post",
        "description": f"Create a Hugo blog post and deploy to {BLOG_URL}. Auto-generates frontmatter, builds with Hugo, rsyncs to nginx.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Post title"},
                "content": {"type": "string", "description": "Markdown body (frontmatter is auto-generated)"},
                "slug": {"type": "string", "description": "URL slug, derived from title if omitted"},
                "draft": {"type": "boolean", "description": "Draft mode? Default false"},
            },
            "required": ["title", "content"],
        },
    },
]

# ── Safe path helper ────────────────────────────────────
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    return path

# ── Tool Handlers ───────────────────────────────────────

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo ", "shutdown", "reboot", "mkfs."]
    for d in dangerous:
        if d in command.lower():
            return f"Error: blocked '{d}'"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return out[:10000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: timeout (30s)"
    except Exception as e:
        return f"Error: {e}"

def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        numbered = [f"{i+1:>4}\t{line}" for i, line in enumerate(lines)]
        if limit and limit < len(numbered):
            numbered = numbered[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(numbered) if numbered else "(empty)"
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        p = safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        p = safe_path(path)
        text = p.read_text()
        if old_text not in text:
            return f"Error: old_text not found in {path}"
        p.write_text(text.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_glob(pattern: str) -> str:
    import glob as g
    try:
        results = sorted(g.glob(pattern, root_dir=WORKDIR))
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"

def run_web_search(query: str, max_results: int = 5) -> str:
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max(max_results, 1)))
        if not results:
            return "(no results)"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '?')}")
            lines.append(f"   {r.get('body', '')[:200]}")
            lines.append(f"   {r.get('href', '')}")
        return "\n".join(lines)
    except ImportError:
        return "Error: duckduckgo_search not installed. Run: pip3 install duckduckgo_search"
    except Exception as e:
        return f"Error: {e}"

def run_web_fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Simple HTML to text
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception as e:
        return f"Error: {e}"

def run_publish_post(title: str, content: str, slug: str = "", draft: bool = False) -> str:
    try:
        # Generate slug
        if not slug:
            slug = re.sub(r"[^\w\s-]", "", title.lower())
            slug = re.sub(r"[-\s]+", "-", slug).strip("-")
            slug = slug[:80] or "untitled"

        # Frontmatter
        date_str = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        fm = (
            f"---\n"
            f"slug: \"{slug}\"\n"
            f"date: '{date_str}'\n"
            f"draft: {str(draft).lower()}\n"
            f"title: '{title}'\n"
            f"---\n\n"
        )
        full = fm + content

        # Write post
        post_path = BLOG_DIR / "content" / "posts" / f"{slug}.md"
        post_path.parent.mkdir(parents=True, exist_ok=True)
        post_path.write_text(full)

        # Build
        r = subprocess.run(["hugo", "--buildFuture"], cwd=BLOG_DIR,
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return f"Error: hugo build failed — {r.stderr[:500]}"

        # Deploy
        r2 = subprocess.run(["rsync", "-az", "--delete", "public/", BLOG_DEPLOY],
                            cwd=BLOG_DIR, capture_output=True, text=True, timeout=30)
        if r2.returncode != 0:
            return f"Error: rsync failed — {r2.stderr[:500]}"

        url = f"{BLOG_URL}/posts/{slug}/"
        return f"✅ Published! {url}"
    except FileNotFoundError:
        return "Error: hugo not found. Install: yum install hugo"
    except Exception as e:
        return f"Error: {e}"

TOOL_HANDLERS = {
    "bash":  run_bash,
    "read":  run_read,
    "write": run_write,
    "edit":  run_edit,
    "glob":  run_glob,
    "web_search": run_web_search,
    "web_fetch":  run_web_fetch,
    "publish_post": run_publish_post,
}

# ── Core Loop ───────────────────────────────────────────

def agent_loop(messages: list, model: str) -> dict:
    total_in, total_out = 0, 0
    turn = 0

    while True:
        turn += 1

        # Sliding window: keep first anchor + last 30 messages
        # Must never split a tool_use/tool_result pair — that causes API 400 errors
        if len(messages) > 30:
            keep_from = len(messages) - 30
            if keep_from > 0:
                first_kept = messages[keep_from]
                if first_kept.get("role") == "user" and isinstance(first_kept.get("content"), list):
                    has_tool_results = any(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in first_kept["content"]
                    )
                    if has_tool_results and messages[keep_from - 1].get("role") == "assistant":
                        keep_from -= 1  # include the paired tool_use message
            messages = [messages[0]] + messages[keep_from:]
            logger.debug("Sliding window applied, kept %d messages", len(messages))

        try:
            response = client.messages.create(
                model=MODEL,
                system=SYSTEM,
                messages=messages,
                tools=TOOLS,
                max_tokens=8000,
            )
        except Exception as e:
            logger.error("API error: %s", e)
            print(f"\n{C['red']}❌ API error: {e}{C['reset']}")
            return {"input_tokens": total_in, "output_tokens": total_out, "cost": None}

        total_in  += response.usage.input_tokens
        total_out += response.usage.output_tokens
        # Filter out thinking blocks (DeepSeek v4 reasoning) — keep only text + tool_use
        filtered = [b for b in response.content if b.type in ("text", "tool_use")]
        if filtered:
            messages.append({"role": "assistant", "content": filtered})
        logger.debug("API call turn=%d in=%d out=%d stop=%s",
                      turn, response.usage.input_tokens,
                      response.usage.output_tokens, response.stop_reason)

        # Print LLM text
        for block in response.content:
            if block.type == "text":
                print(f"\n{C['cyan']}{block.text}{C['reset']}")

        # Done if no tool calls
        if response.stop_reason != "tool_use":
            cost = calc_cost(model, total_in, total_out)
            return {"input_tokens": total_in, "output_tokens": total_out,
                    "cost": cost, "turns": turn}

        # Execute tools
        results = []
        for block in response.content:
            if block.type == "tool_use":
                name = block.name
                inp = block.input
                handler = TOOL_HANDLERS.get(name)

                # Display
                icons = {"bash":"$","read":"📖","write":"✏️","edit":"🔧","glob":"🔍",
                         "web_search":"🔎","web_fetch":"🌐","publish_post":"📝"}
                icon = icons.get(name, "🔧")
                inp_preview = str({k: (str(v)[:60]+"...") if len(str(v))>60 else v for k,v in inp.items()})
                print(f"\n{C['yellow']}  {icon} {name} {inp_preview}{C['reset']}")

                # Filter to only accepted params
                if handler:
                    sig = inspect.signature(handler)
                    valid = {k: v for k, v in inp.items() if k in sig.parameters}
                    try:
                        output = handler(**valid)
                        logger.info("TOOL %s %s → %s", name,
                                    json.dumps(inp, ensure_ascii=False)[:200],
                                    output[:200])
                    except Exception as e:
                        output = f"Error: {e}"
                        logger.error("TOOL %s %s ERROR: %s", name,
                                     json.dumps(inp, ensure_ascii=False)[:200], e)
                else:
                    output = f"Unknown tool: {name}"
                    logger.warning("TOOL unknown: %s", name)

                preview = output[:200] + ("..." if len(output) > 200 else "")
                if preview:
                    print(f"{C['dim']}  → {preview}{C['reset']}")

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

        messages.append({"role": "user", "content": results})


# ── Interactive Entry ───────────────────────────────────

def main():
    # tolerate non-UTF-8 / broken pipe input
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logger.info("═" * 40)
    logger.info("SESSION START model=%s cwd=%s", MODEL, WORKDIR)

    print(f"{C['bold']}╔══════════════════════════════════════╗{C['reset']}")
    print(f"{C['bold']}║        🧠 MiniAgent (VPS)           ║{C['reset']}")
    print(f"{C['bold']}╚══════════════════════════════════════╝{C['reset']}")
    print(f"  {C['dim']}model:{C['reset']} {MODEL}")
    print(f"  {C['dim']}cwd:{C['reset']}   {WORKDIR}")
    print(f"  {C['dim']}blog:{C['reset']}  {BLOG_URL}")
    print(f"  {C['dim']}log:{C['reset']}   {LOG_FILE}")
    print()
    print(f"  {C['dim']}/help /h /clear /system /tokens /cost | /nohistory /stable /restore /memory | q to quit{C['reset']}")
    print()

    history: list = []
    session_in, session_out = 0, 0
    session_cost = 0.0
    turn_costs: list[float] = []
    nohistory: bool = False  # when True, each query is a fresh start

    while True:
        try:
            raw = input(f"{C['green']}你 › {C['reset']}")
        except (EOFError, KeyboardInterrupt, UnicodeDecodeError):
            print()
            break

        query = raw.strip()
        if not query:
            continue

        if query.lower() in ("q", "exit", "quit"):
            cost_str = f"${session_cost:.6f}" if session_cost > 0 else "$0.00"
            logger.info("SESSION END %di/%do tokens cost=%s", session_in, session_out, cost_str)
            print(f"{C['dim']}Bye! {session_in}i / {session_out}o tokens | cost: {cost_str}{C['reset']}")
            break

        if query == "/clear":
            history.clear()
            session_in = session_out = 0
            session_cost = 0.0
            turn_costs.clear()
            print(f"{C['dim']}🧹 History cleared{C['reset']}\n")
            continue

        if query in ("/help", "/h"):
            print(f"""
{C['bold']}╔══════════════════════════════════════╗{C['reset']}
{C['bold']}║        MiniAgent 指令帮助            ║{C['reset']}
{C['bold']}╚══════════════════════════════════════╝{C['reset']}

{C['yellow']}内置命令:{C['reset']}
  {C['green']}/help, /h{C['reset']}       显示此帮助
  {C['green']}/clear{C['reset']}          清除会话历史 & token 计数器
  {C['green']}/system{C['reset']}         显示 system prompt 和可用工具
  {C['green']}/tokens{C['reset']}         当前会话 token 用量和费用
  {C['green']}/cost{C['reset']}           逐轮费用明细
  {C['green']}/nohistory{C['reset']}      开关：每轮对话独立（不携带上下文）
  {C['green']}/stable{C['reset']}         git commit + tag 当前 agent.py 为 stable
  {C['green']}/restore{C['reset']}        从 stable tag 恢复 agent.py（需重启）
  {C['green']}/memory{C['reset']}        显示 AGENT.md 记忆文件
  {C['green']}q / exit / quit{C['reset']} 退出

{C['yellow']}直接输入自然语言即可:{C['reset']}
  搜东西 / 写代码 / 发博客 / 跑命令 …
  例如：{C['dim']}"写一篇关于 GPT-5 的博客"  "搜特斯拉最新新闻"  "跑 df -h"{C['reset']}

{C['yellow']}可用工具:{C['reset']}
  {C['cyan']}bash{C['reset']}         执行 shell 命令
  {C['cyan']}read{C['reset']}         读取文件（带行号）
  {C['cyan']}write{C['reset']}        写入/覆盖文件
  {C['cyan']}edit{C['reset']}         查找替换文件内容
  {C['cyan']}glob{C['reset']}         按模式搜索文件
  {C['cyan']}web_search{C['reset']}   搜索网页 (DuckDuckGo)
  {C['cyan']}web_fetch{C['reset']}    抓取网页内容
  {C['cyan']}publish_post{C['reset']} 发布博客到 {BLOG_URL}

{C['dim']}blog: {BLOG_URL} | log: {LOG_FILE}{C['reset']}
""")
            continue

        if query == "/system":
            print(f"\n{C['dim']}─── System Prompt ───{C['reset']}")
            print(SYSTEM)
            print(f"{C['dim']}─── Tools: {', '.join(t['name'] for t in TOOLS)} ───{C['reset']}\n")
            continue

        if query == "/tokens":
            cost_str = f"${session_cost:.6f}" if session_cost > 0 else "$0.00"
            print(f"{C['dim']}Session: {session_in}i / {session_out}o | cost: {cost_str}{C['reset']}\n")
            continue

        if query == "/cost":
            if not turn_costs:
                print(f"{C['dim']}$0.00 — no turns yet{C['reset']}\n")
            else:
                for i, tc in enumerate(turn_costs, 1):
                    print(f"{C['dim']}  Turn {i}: ${tc:.6f}{C['reset']}")
                print(f"{C['dim']}  Total: ${session_cost:.6f}{C['reset']}\n")
            continue

        if query == "/nohistory":
            nohistory = not nohistory
            status = "ON (each query fresh)" if nohistory else "OFF (normal)"
            print(f"{C['dim']}🔁 No-history mode: {status}{C['reset']}\n")
            continue

        if query == "/stable":
            import subprocess as sp
            r = sp.run(["git", "-C", str(Path(__file__).resolve().parent),
                        "add", "agent.py"],
                       capture_output=True, text=True, timeout=10)
            r = sp.run(["git", "-C", str(Path(__file__).resolve().parent),
                        "commit", "-m", f"stable: {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}"],
                       capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                sp.run(["git", "-C", str(Path(__file__).resolve().parent),
                        "tag", "-f", "stable"], capture_output=True, timeout=10)
                print(f"{C['dim']}✅ Stable version archived (commit + tag 'stable'){C['reset']}\n")
            else:
                print(f"{C['dim']}ℹ️  {r.stdout.strip() or r.stderr.strip()}{C['reset']}\n")
            continue

        if query == "/restore":
            import subprocess as sp
            agent_dir = str(Path(__file__).resolve().parent)
            r = sp.run(["git", "-C", agent_dir, "checkout", "stable", "--", "agent.py"],
                       capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                print(f"{C['red']}♻️  agent.py restored to 'stable'. Restart required!{C['reset']}\n")
            else:
                print(f"{C['red']}❌ Restore failed: {r.stderr.strip()}{C['reset']}\n")
            continue

        if query == "/memory":
            md = WORKDIR / "AGENT.md"
            if md.exists():
                print(f"\n{C['dim']}── AGENT.md ──{C['reset']}")
                print(md.read_text(encoding="utf-8"))
                print(f"{C['dim']}── End ──{C['reset']}\n")
            else:
                print(f"{C['dim']}No AGENT.md file found.{C['reset']}\n")
            continue

        history.append({"role": "user", "content": query})
        logger.info("USER %s", query[:300])
        result = agent_loop(history, MODEL)

        if "turns" in result:
            session_in  += result["input_tokens"]
            session_out += result["output_tokens"]
            tc = result.get("cost")
            if tc is not None:
                session_cost += tc
                turn_costs.append(tc)
                cost_display = f"${tc:.6f}"
            else:
                cost_display = "$-"
            logger.info("TURN %d turns +%di/+%do cost=%s",
                        result["turns"], result["input_tokens"],
                        result["output_tokens"], cost_display)
            print(f"\n{C['dim']}[{result['turns']} turns, "
                  f"+{result['input_tokens']}i / +{result['output_tokens']}o"
                  f" | cost: {cost_display}]{C['reset']}\n")

        if nohistory:
            history.clear()
            logger.debug("No-history: cleared history")


if __name__ == "__main__":
    main()
