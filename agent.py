#!/usr/bin/env python3
"""
MiniAgent — ReAct agent for VPS
  coding tools (bash/read/write/edit/glob) + web_search + web_fetch + publish_post
  pure context compression — no sliding window, LLM summarization only

Usage: python3 agent.py
       python3 agent.py /restore  (rollback to last git commit)
       python3 agent.py /undo     (undo last modification)
"""
from __future__ import annotations
import os, sys, subprocess, json, re, urllib.request, urllib.parse, inspect, logging, py_compile
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

if not API_KEY and "/restore" not in sys.argv and "/undo" not in sys.argv:
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

# ── Git & Restore Helpers ───────────────────────────────
def git_commit(message: str):
    """Auto-commit changes to keep a 'known good' state."""
    try:
        subprocess.run(["git", "add", "."], cwd=WORKDIR, check=True)
        # Check if there are changes to commit
        r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=WORKDIR)
        if r.returncode != 0:
            subprocess.run(["git", "commit", "-m", message], cwd=WORKDIR, check=True)
            logger.info("Auto-committed: %s", message)
    except Exception as e:
        logger.warning("Auto-commit failed: %s", e)

def run_restore():
    """Rollback to the last git commit."""
    print(f"🔄 Restoring to last stable commit...")
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=WORKDIR, check=True)
        print("✅ Restored successfully.")
    except Exception as e:
        print(f"❌ Restore failed: {e}")
    sys.exit(0)

def run_undo():
    """Undo the last change using git reflog."""
    print(f"↩️  Undoing last change...")
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD@{1}"], cwd=WORKDIR, check=True)
        print("✅ Undone successfully.")
    except Exception as e:
        print(f"❌ Undo failed: {e}")
    sys.exit(0)

# Handle CLI commands
if "/restore" in sys.argv: run_restore()
if "/undo" in sys.argv: run_undo()

# ── Git safety: verify SSH remotes ──────────────────────
def _check_ssh_remote(path: Path, repo_name: str):
    try:
        r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=path,
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and "https://" in r.stdout:
            logger.error("⚠️  %s remote uses HTTPS! Fix: git remote set-url origin git@github.com:...", repo_name)
    except Exception:
        pass

_check_ssh_remote(BLOG_DIR, "~/aipulse")
_check_ssh_remote(WORKDIR, "miniagent")

# ── Hooks Engine ───────────────────────────────────────
HOOKS_FILE = WORKDIR / "hooks.json"
HOOKS: dict = {}  # event_name -> list of {matcher, command}

def load_hooks():
    global HOOKS
    if HOOKS_FILE.exists():
        try:
            cfg = json.loads(HOOKS_FILE.read_text())
            HOOKS = cfg.get("hooks", {})
            logger.info("Loaded hooks: %d event types", len(HOOKS))
        except Exception as e:
            logger.error("Failed to load hooks.json: %s", e)
            HOOKS = {}
    else:
        HOOKS = {}

def dispatch_hooks(event: str, context: dict) -> tuple[bool, list[str]]:
    """Run all matching hooks for an event. Returns (allowed, messages).
    allowed=False means blocked (exit code 2)."""
    handlers = HOOKS.get(event, [])
    if not handlers:
        return True, []

    ctx_json = json.dumps(context, ensure_ascii=False, default=str)
    allowed = True
    messages = []

    for h in handlers:
        matcher = h.get("matcher", "")
        if matcher and event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            tool_name = context.get("tool_name", "")
            if not re.search(matcher, tool_name):
                continue

        cmd = h.get("command", "")
        if not cmd:
            continue

        try:
            r = subprocess.run(
                cmd, shell=True, input=ctx_json, capture_output=True, text=True,
                timeout=10, cwd=WORKDIR
            )
            out = (r.stdout + r.stderr).strip()
            if r.returncode == 2:
                allowed = False
                logger.warning("HOOK BLOCK %s: %s → %s", event, matcher, out[:200])
                messages.append(f"🚫 Hook blocked: {out[:300]}")
            else:
                logger.debug("HOOK %s: %s → rc=%d %s", event, matcher, r.returncode, out[:100])
                if out:
                    messages.append(out[:300])
        except subprocess.TimeoutExpired:
            logger.warning("HOOK TIMEOUT %s: %s", event, matcher)
        except Exception as e:
            logger.warning("HOOK ERROR %s: %s → %s", event, matcher, e)

    return allowed, messages

load_hooks()

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
AGENT_MD = WORKDIR / "AGENT.md"
if AGENT_MD.exists():
    AGENT_INSTRUCT = AGENT_MD.read_text(encoding="utf-8")

MEMORY_MD = WORKDIR / "MEMORY.md"
AGENT_MEMORY = ""
if MEMORY_MD.exists():
    AGENT_MEMORY = MEMORY_MD.read_text(encoding="utf-8")
    lines = AGENT_MEMORY.splitlines()
    if len(lines) > 200:
        AGENT_MEMORY = "\n".join(lines[-200:])
        logger.warning("MEMORY.md >200 lines, truncated to last 200")

SYSTEM = f"""You are a coding + writing agent on a VPS (AlmaLinux 9, {WORKDIR}).
Use tools proactively. Write code, search the web, publish blog posts.

Rules:
- Act directly, don't explain before doing.
- Read files before editing them.
- For blog posts: use publish_post tool — it handles frontmatter + build + deploy.
- Search the web before writing about current events.
- Keep responses short — the user sees tool outputs.
- Blog posts at {BLOG_URL}

── Agent Instructions ({WORKDIR}/AGENT.md) ──
{AGENT_INSTRUCT}
── End Instructions ──

── Persistent Memory ({WORKDIR}/MEMORY.md) ──
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

def check_syntax(path: str, content: str) -> bool:
    """Check syntax if the file is a Python file."""
    if not path.endswith(".py"):
        return True
    tmp = Path(f"{path}.tmp")
    try:
        tmp.write_text(content)
        py_compile.compile(str(tmp), doraise=True)
        return True
    except Exception as e:
        logger.error("Syntax check failed for %s: %s", path, e)
        return False
    finally:
        if tmp.exists(): tmp.unlink()

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
    if not check_syntax(path, content):
        return f"Error: syntax check failed. Refusing to write to {path}."
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
        new_content = text.replace(old_text, new_text, 1)
        if not check_syntax(path, new_content):
            return f"Error: syntax check failed. Refusing to edit {path}."
        p.write_text(new_content)
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_glob(pattern: str) -> str:
    try:
        results = sorted(str(p) for p in WORKDIR.glob(pattern))
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
        r = subprocess.run(["rsync", "-avz", "--delete", "public/", BLOG_DEPLOY],
                           cwd=BLOG_DIR, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return f"Error: deploy failed — {r.stderr[:500]}"

        return f"✅ Published: {BLOG_URL}/posts/{slug}/"
    except Exception as e:
        return f"Error: {e}"

# ── Agent Loop ──────────────────────────────────────────

def main():
    print(f"{C['bold']}{C['cyan']}MiniAgent{C['reset']} starting...")
    history = [{"role": "system", "content": SYSTEM}]

    # Load persistent history if exists? (Optional, currently session-based)
    
    while True:
        try:
            user_input = input(f"{C['green']}user>{C['reset']} ").strip()
            if not user_input: continue
            if user_input.lower() in ("exit", "quit"): break
            
            history.append({"role": "user", "content": user_input})
            
            # The Loop
            while True:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=SYSTEM,
                    messages=[h for h in history if h["role"] != "system"],
                    tools=TOOLS,
                )
                
                # Handle Assistant Response
                assistant_text = ""
                tool_calls = []
                for block in resp.content:
                    if block.type == "text":
                        assistant_text += block.text
                    elif block.type == "tool_use":
                        tool_calls.append(block)
                
                if assistant_text:
                    print(f"{C['cyan']}agent>{C['reset']} {assistant_text}")
                    history.append({"role": "assistant", "content": assistant_text})
                
                if not tool_calls:
                    # Task done for this turn, auto-commit
                    git_commit(f"task: {user_input[:50]}")
                    break
                
                # Execute Tools
                for tc in tool_calls:
                    tname = tc.name
                    targs = tc.input
                    tid = tc.id
                    
                    print(f"{C['yellow']}tool:{C['reset']} {tname}({json.dumps(targs, ensure_ascii=False)})")
                    
                    # Hooks: PreToolUse
                    allowed, hook_msgs = dispatch_hooks("PreToolUse", {"tool_name": tname, "args": targs})
                    if not allowed:
                        result = "\n".join(hook_msgs) or "Blocked by hook"
                    else:
                        if tname == "bash": result = run_bash(**targs)
                        elif tname == "read": result = run_read(**targs)
                        elif tname == "write": result = run_write(**targs)
                        elif tname == "edit": result = run_edit(**targs)
                        elif tname == "glob": result = run_glob(**targs)
                        elif tname == "web_search": result = run_web_search(**targs)
                        elif tname == "web_fetch": result = run_web_fetch(**targs)
                        elif tname == "publish_post": result = run_publish_post(**targs)
                        else: result = f"Error: unknown tool {tname}"
                    
                    # Hooks: PostToolUse
                    _, post_msgs = dispatch_hooks("PostToolUse", {"tool_name": tname, "args": targs, "result": result})
                    if post_msgs:
                        result += "\n\n-- Hook Output --\n" + "\n".join(post_msgs)

                    print(f"{C['dim']}{result[:200]}{'...' if len(result)>200 else ''}{C['reset']}")
                    
                    # Update history with tool result
                    # Note: Anthropic requires assistant message with tool_use before tool results
                    if not assistant_text:
                        # If model only sent tool_use, we must still add it to history
                        history.append({"role": "assistant", "content": resp.content})
                    
                    history.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": result,
                            }
                        ],
                    })

        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except Exception as e:
            logger.exception("Fatal error in loop")
            print(f"{C['red']}Error:{C['reset']} {e}")
            break

if __name__ == "__main__":
    main()
