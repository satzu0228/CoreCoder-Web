# CLAUDE.md

## 项目是什么

CoreCoder-Web 是对开源项目 [CoreCoder](https://github.com/he-yufeng/CoreCoder)（一个约 1,000 行的极简 CLI coding agent）的二次开发，目标是把它扩展成一个 **Web 化、支持人机协作（human-in-the-loop）审批的 coding agent**。

不是给 CoreCoder 套一个聊天网页。真正要做的是两件事：

1. 把终端交互循环改造成 Web 交互（workspace 绑定、SSE 流式事件、执行过程可视化）
2. 在 agent 的工具执行层加入人机协作确认机制：`edit_file` 写入前、`bash` 命中危险命令时，先弹出确认，用户批准后才真正执行

第 2 点是这个项目的技术含量所在，也是设计和开发时应该优先打磨的部分。

## 当前状态

`corecoder/` 目录下的代码目前和上游 CoreCoder **完全一致**（`git diff upstream/main main` 无差异）。Web 层、确认机制、FastAPI/Vue 前端都还没有开始写，仍处于设计阶段。

不要假设 `web/` 目录、`events.py`、`confirm_registry.py` 等已存在——落地前请先确认代码库当前的真实状态，不要凭设计文档推断代码已经存在。

## 权威设计文档

详细设计全部写在 `docs/MVP 需求文档.md` 里，是这个项目所有架构决策的唯一权威来源。做任何实现前应先读它，尤其是：

- 3.1 节：为什么用「单次调用内阻塞」而不是「分两轮对话」实现确认
- 3.2 节：开发顺序——先在 `EditFileTool`/`BashTool` 里各自写死确认逻辑，两者都跑通之后才提炼 `ConfirmableTool` 抽象，不要一开始就设计抽象基类
- 3.3 节：「用户拒绝确认」是独立于「参数错误」「执行错误」的第三类结果，不能套进 `except Exception` 里拍扁
- 3.4 节：`session.py` 现有的对话历史持久化和新增的运行时状态（`RUNNING`/`WAIT_CONFIRM`/`DONE`）是两个概念，不要混在一起
- 7 节：安全设计——只绑 `127.0.0.1`、URL 带随机 token、路径越界校验、bash 黑名单确认

`docs/学习记录.md` 和 `docs/开发注意点.md` 是开发过程中的学习笔记和注意事项，可作为背景参考，不是设计依据。

## 硬约束

- **不改动 `llm.py`。** API 调用、stream、retry、provider 兼容这一层保持原样，新代码不直接调 LLM API。
- **不重写 agent 主循环。** `agent.py` 里 `chat()` 的核心结构（问模型 → 判断 tool_calls → 执行 → 继续）保持不变，扩展点集中在工具执行阶段的事件回调和确认机制上，通过模块级事件总线 `events.emit` 打通，而不是改 `_exec_tool` 的调度逻辑。
- **单用户、单 workspace 是 MVP 的前提假设，不是疏漏。** `ConfirmRegistry`、事件总线等模块级单例在这个假设下是安全的。如果要往多 workspace/多用户扩展，需要改成按 `session_id` 隔离，这是 v2 的事，不要在 MVP 阶段抢先做。
- **不建独立 Diff 页面，不新增 `workspace_search`/`analyze_project` 之类的工具。** agent 靠 `glob`+`read_file`+`grep` 组合已经够用，专门建工具收益不明确。

## 目录结构

```
corecoder/          agent runtime（agent.py / llm.py / context.py / tools/ 等），目前与上游一致
docs/                项目设计文档与开发笔记（MVP 需求文档是唯一权威来源）
tests/               pytest 测试
.github/workflows/   CI（跑 pytest + ruff + compileall）
README.md / README_CN.md   项目展示用 README，面向 GitHub 访客和技术面试官
```

Web 层代码（`corecoder/web/` 下的 `server.py`/`app.py`/`routes/`/`events.py`/`confirm_registry.py`/`workspace_fs.py`）按 MVP 文档第 4 节的设计逐步搭建，尚未创建。

## 开发与验证

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q      # 跑测试
ruff check corecoder tests      # lint
python -m compileall -q corecoder tests
```

CI（`.github/workflows/ci.yml`）在 Ubuntu/macOS/Windows 上跑 Python 3.10–3.13 的测试矩阵，提交前应保证这三项都过。

## 与上游 CoreCoder 的关系

`corecoder/` 里未改动的部分（`llm.py` 的 provider 适配、`context.py` 的三层压缩、`session.py` 的对话历史持久化、`tools/` 里除 `edit.py`/`bash.py` 之外的工具）应当保持和上游一致的风格，遇到 bug 优先考虑是否也存在于上游、要不要上报，而不是想当然地大改。
