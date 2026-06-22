# MiniAgent — Persistent Memory

> Auto-generated. Keep <200 lines; if exceeded, compress with summaries.
> Last update: 2025-06-22 (compression engine installed)

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
- `/restore` → `git checkout stable -- agent.py` (then restart agent)
- `/context` → show context overview (token usage, compression state, file stats)
- `/nohistory` → reset conversation each turn (no carry-over)

## Blog (Hugo)
- Theme: `hugo-coder` (check `/root/aipulse/themes/`)
- Build: `hugo --source /root/aipulse --destination /var/www/aitracker`
- `publish_post` tool handles frontmatter + build + deploy automatically

## Context Management (v2 — Compression)
- **NO SLIDING WINDOW** — old approach dropped messages, causing amnesia
- New: when estimated tokens > 60,000, LLM compresses old messages into a bullet summary
- Keeps: first message (anchor) + compressed summary + last 24 messages
- Compression calls a small API request (max 400 tokens output)
- Fallback: if compression fails or still too large → hard cutoff preserving tool_use/tool_result pairs
- agent.md = instructions (loaded into system prompt). MEMORY.md = this file (persistent memory).

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
- **Compression replaces sliding window** (2025-06-22): Old sliding window caused amnesia after ~15 turns. Now LLM summarizes old context.
- **`/stable` push bug fixed**: Old code didn't `git push` after commit+tag. Now pushes both `main` and `--tags`.
- **`git commit` rejects empty changes**: `/stable` shows stdout/stderr when this happens.
- **agent.md vs MEMORY.md**: `agent.md` = instructions. `MEMORY.md` = persistent memory (this file).

## Session Log
- 2025-06-22: Replaced sliding window with compression-based context. Token threshold: 60k. Keep recent: 24 messages.
- 2025-06-22: Fixed /stable push bug (added `git push origin main` and `git push origin --tags`).
- 2025-06-22 earlier: Created dual memory files (agent.md + MEMORY.md), /memory command. Stable at a0c605e.
