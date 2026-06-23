# MiniAgent 优化建议方案

针对当前项目，以下是四个核心维度的优化建议：

## 1. 健壮性优化 (Robustness)
* **多模型降级 (Fallback)**: 当主模型（如 DeepSeek）报错 402（余额不足）或 500 时，自动切换到备份模型（如 GPT-4o-mini）。
* **断点续传 (State Persistence)**: 将对话历史实时保存到 `history.json`，重启后可自动恢复进度。
* **安全沙箱**: 增强 `bash` 工具的过滤逻辑，防止 AI 执行 `rm -rf /` 等高危操作。

## 2. 智能化优化 (Intelligence)
* **项目全局视野**: 增加 `search_repo` 工具，让 Agent 自动索引项目所有文件，而不仅仅是当前操作的文件。
* **任务规划 (Planning)**: 引入“先规划、后执行”模式，Agent 在执行复杂任务前先生成 `todo.md`。

## 3. 用户体验 (User Experience)
* **远程管理**: 集成 Telegram Bot，让你能通过手机随时给 VPS 发送指令。
* **进度可视化**: 在你的 Hugo 博客上生成一个隐藏的 `/agent-status` 页面，实时展示 Agent 的工作流。

## 4. API 成本控制
* **余额预警**: 实时解析 API 返回的消耗信息，余额不足时提前通知。
* **上下文压缩**: 自动识别并总结过长的历史对话，减少 Token 浪费。

---
*你可以直接在终端运行 `cat OPTIMIZE.md` 查看此文件内容。*
