# MiniAgent — Persistent Memory

> Auto-generated. Keep <200 lines; if exceeded, compress with summaries.
> Last update: auto-refreshed each session.

## Critical Paths
| What | Path |
|------|------|
| Repo root | `/root/miniagent` |
| Blog dir (Hugo) | `/root/aipulse` |
| Nginx deploy | `/var/www/aitracker` |
| Blog URL | `https://aipulse.lol` |
| Log file | `/root/miniagent/agent.log` (5MB×5 rotation) |
| Workdir | `/root/miniagent` |

## Environment (from agent.py config)
| Var | Value |
|-----|-------|
| ANTHROPIC_BASE_URL | env var (API endpoint) |
| ANTHROPIC_API_KEY | env var |
| ANTHROPIC_MODEL | `deepseek-v4-pro` (default) |
| Timezone | CST (UTC+8) |

## Git Remotes
| Name | URL |
|------|-----|
| origin | `git@github.com:mbwjs/miniagent.git` |

Auth: SSH key already configured.

## Stable Tag Protocol
- `/stable` → `git tag -f stable HEAD && git push origin stable`
- `/restore` → `git checkout stable -- agent.py`
- `/nohistory` → reset conversation

## Blog (Hugo)
- Theme: `hugo-coder` (or check `/root/aipulse/themes/`)
- Build: `hugo --source /root/aipulse --destination /var/www/aitracker`
- `publish_post` tool auto-handles frontmatter + build + deploy

## Agent Behavior Rules (condensed)
1. Act directly — no pre-explanation.
2. Read before edit.
3. Web-search before writing current events.
4. Keep responses short; user sees tool outputs.
5. `publish_post` is the only blog-publish path.
6. Respect `<200 line` memory constraint; compress as needed.

## Pricing ($/M tokens)
| Model | Input | Output |
|-------|-------|--------|
| deepseek-v4-pro | $0.14 | $1.10 |
| claude-sonnet-4-6 | $3.00 | $15.00 |

## Session History
(append per session; compress when >200 lines)

### 2025-06-22 (session)
- Stable tag created: `bcb65c7` ("stable: 2026-06-23 02:33:59")
- AGENT.md created as persistent memory file
- Repo: 6 commits on main, synced with origin
