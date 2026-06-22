# MiniAgent — Persistent Memory

> Auto-generated. Keep <200 lines; if exceeded, compress with summaries.
> Last update: 2025-06-22 session

## Critical Paths
| What | Path |
|------|------|
| Repo root | `/root/miniagent` |
| Blog dir (Hugo) | `/root/aipulse` |
| Nginx deploy | `/var/www/aitracker` |
| Blog URL | `https://aipulse.lol` |
| Log file | `/root/miniagent/agent.log` (5MB×5 rotation) |
| Workdir | `/root/miniagent` |

## Environment
| Var | Value |
|-----|-------|
| ANTHROPIC_BASE_URL | env var |
| ANTHROPIC_API_KEY | env var |
| ANTHROPIC_MODEL | `deepseek-v4-pro` (default) |
| Timezone | CST (UTC+8) |

## Git
- Remote: `git@github.com:mbwjs/miniagent.git` (SSH key configured)
- `/stable` → `git add agent.py` → commit → `tag -f stable` → **push origin main + push --tags**
- `/restore` → `git checkout stable -- agent.py` (then restart)
- `/nohistory` → reset conversation (no carry-over)

## Blog (Hugo)
- Theme: `hugo-coder` (check `/root/aipulse/themes/`)
- Build: `hugo --source /root/aipulse --destination /var/www/aitracker`
- `publish_post` tool handles frontmatter + build + deploy automatically

## Core Rules (for agent)
1. Act directly — no pre-explanation.
2. Read files before editing.
3. Web-search before writing about current events.
4. Keep responses short; user sees tool outputs.
5. `publish_post` is the only blog-publish path.
6. Respect <200 line memory constraint; compress when needed.

## Pricing ($/M tokens)
| Model | Input | Output |
|-------|-------|--------|
| deepseek-v4-pro | $0.14 | $1.10 |
| claude-sonnet-4-6 | $3.00 | $15.00 |

## Known Issues / Lessons Learned
- **Sliding window causes amnesia**: Context older than ~15 turns gets dropped. I may forget what user asked earlier. Check AGENT.md or ask user.
- **`/stable` bug fixed**: Old code didn't `git push` after commit+tag. Now pushes both `main` and `--tags`.
- **`git commit` rejects empty changes**: If agent.py hasn't been modified, commit fails. `/stable` now handles this gracefully.
- **agent.md vs AGENT.md**: `agent.md` = instructions loaded into system prompt at boot. `AGENT.md` = persistent memory (this file). Both injected.

## Session Log
- 2025-06-22: Created AGENT.md, agent.md. Fixed /stable push bug. stable tag at a0c605e (feat: dual memory files, /memory command).
- 2025-06-22 earlier: Initial setup, stable tag created at bcb65c7.
