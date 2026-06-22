# 🧠 MiniAgent

VPS 上的 ReAct agent —— 写代码、搜网页、发博客，全在命令行里搞定。

> **不丢记忆 + 极低成本 + 单文件 800 行 = 一个真正能跑长任务的 VPS agent。**

## 安装

```bash
# 1. 设置 API key
export ANTHROPIC_API_KEY="sk-..."

# 2. 可选：切换模型/厂商
export ANTHROPIC_BASE_URL="https://api.deepseek.com"
export ANTHROPIC_MODEL="deepseek-v4-pro"

# 3. 安装依赖
pip3 install anthropic duckduckgo_search
```

## 使用

```bash
python3 agent.py
```

输入自然语言即可，agent 会在 ReAct 循环中调用工具（bash、read、write、edit、glob、web_search、web_fetch、publish_post）完成任务。

## 内置命令

| 命令 | 作用 |
|---|---|
| `/help` / `/h` | 显示完整帮助 |
| `/clear` | 清除会话历史 & token 计数器 |
| `/system` | 查看 system prompt 和可用工具 |
| `/tokens` | 当前会话 token 用量和费用 |
| `/cost` | 逐轮费用明细 |
| `/nohistory` | 开关：每轮对话独立（不携带上下文） |
| `/compress` | 手动触发上下文压缩 |
| `/stable` | git commit + tag 当前 `agent.py` 为 stable |
| `/restore` | 从 stable tag 恢复 `agent.py`（需重启） |
| `/memory` | 显示 MEMORY.md 记忆文件 |
| `/context` | 上下文总览（token / 费用 / 压缩 / 文件状态） |
| `q` / `exit` / `quit` | 退出 |

## Agent 可用工具

- **bash** — 执行 shell 命令（危险命令拦截，30 秒超时）
- **read** — 读取文件内容（带行号）
- **write** — 写入/覆盖文件（自动创建父目录）
- **edit** — 查找替换文件中的第一处匹配
- **glob** — 按模式搜索文件
- **web_search** — DuckDuckGo 网页搜索
- **web_fetch** — 抓取网页内容
- **publish_post** — 一键发布 Hugo 博客到 `aipulse.lol`

## 博客发布

需要安装 Hugo，并在 `agent.py` 中配置路径：

- `BLOG_DIR = ~/aipulse`（Hugo 站点根目录）
- `BLOG_DEPLOY = /var/www/aitracker`（nginx 文档根目录）

Agent 自动生成 frontmatter，执行 `hugo --buildFuture`，rsync 部署到目标路径。

## 为什么选择 MiniAgent？

| 优点 | 说明 |
|---|---|
| 🧠 **LLM 压缩上下文** | 不是滑动窗口丢消息。超 60k token 时，调用 API 自动把旧消息摘要成 bullet points，保留全部语义不丢失关键决策。 |
| 📝 **双文件记忆系统** | `AGENT.md` = 行为指令，`MEMORY.md` = 跨会话持久记忆。随时编辑控制 agent 行为，无需改代码。 |
| 💰 **极低成本** | 默认 `deepseek-v4-pro`（$0.14/M input，$1.10/M output），一次压缩只需几分钱。模型可切换，每轮精确计费。 |
| 🧩 **单文件，零框架** | 仅 800 行 Python，直接调 Anthropic API tool_use，无 LangChain/AutoGPT 等重型依赖。 |
| 🚀 **一键发博客** | `publish_post` 工具自动生成 Hugo frontmatter → 构建 → rsync 部署到 nginx，全链路自动化。 |
| 🔒 **安全硬拦截** | `rm -rf /`、`sudo`、`shutdown`、`reboot`、`mkfs` 直接拒绝，文件路径限定在工作目录，bash 30 秒超时。 |
| 👁️ **工具执行透明** | 每个工具调用实时显示 icon + 输入参数 + 输出预览，全程可见不黑盒。 |
| 🛠️ **运维友好** | `/stable` 一键 git tag、`/restore` 回滚、`/nohistory` 无上下文模式、`/context` 全貌诊断。 |

## 架构

- **ReAct 循环**：Agent 收到查询 → 决定调用哪些工具 → 执行工具 → 结果反馈 → 循环直到完成
- **上下文压缩**：估算 token 超 60k 时，LLM 将旧消息摘要成 bullet points（不是丢弃）。保留首条锚定消息 + 压缩摘要 + 最近 24 条消息完整。
- **费用追踪**：逐轮 / 会话 token 统计，按模型计价
- **日志**：`agent.log` 滚动日志（5MB × 5 备份）

## 安全

- `rm -rf /`、`sudo`、`shutdown`、`reboot`、`mkfs` 等危险命令被拦截
- 所有文件路径限制在 `WORKDIR` 内解析
- bash 命令 30 秒超时
