# CLAUDE.md

## 项目是什么

CoreCoder-Web 是对开源项目 [CoreCoder](https://github.com/he-yufeng/CoreCoder)（一个约 1,000 行的极简 CLI coding agent）的二次开发，目标是把它扩展成一个 **Web 化、支持人机协作（human-in-the-loop）审批的 coding agent**。

不是给 CoreCoder 套一个聊天网页。真正要做的是两件事：

1. 把终端交互循环改造成 Web 交互（workspace 绑定、SSE 流式事件、执行过程可视化）
2. 在 agent 的工具执行层加入人机协作确认机制：Web 模式下 `edit_file`/`write_file` 写入前、`bash` 命中危险命令时，先弹出确认，用户批准后才真正执行

第 2 点是这个项目的技术含量所在，也是设计和开发时应该优先打磨的部分。

## 当前状态

MVP 的 Web 核心闭环已经落地：`corecoder/web/`、Vue3 前端、SSE 工具事件、文件树、Monaco Diff 和确认流程均存在。2026-08-08 完成了一轮集成修复，包括 CLI `edit_file` 兼容、通用 `request_confirmation()`、并行确认串行化、Web 文件工具路径约束、`write_file` 确认以及前端 CI/发布构建。

当前阶段是体验和可靠性优化，不再是设计阶段。判断实现状态时以代码、测试和 `docs/开发日志.md` 为准；`docs/MVP 需求文档.md` 保留设计意图，允许开发日志记录经过验证的实现偏差。

## 权威设计文档

详细设计全部写在 `docs/MVP 需求文档.md` 里，是这个项目所有架构决策的唯一权威来源。做任何实现前应先读它，尤其是：

- 3.1 节：为什么用「单次调用内阻塞」而不是「分两轮对话」实现确认
- 3.2 节：确认最初在具体工具中验证，现已提炼为 `web/_confirmable.py` 的通用函数；不要再复制 registry 调用序列
- 3.3 节：「用户拒绝确认」是独立于「参数错误」「执行错误」的第三类结果，不能套进 `except Exception` 里拍扁
- 3.4 节：`session.py` 现有的对话历史持久化和新增的运行时状态（`RUNNING`/`WAIT_CONFIRM`/`DONE`）是两个概念，不要混在一起
- 7 节：安全设计——只绑 `127.0.0.1`、URL 带随机 token、路径越界校验、bash 黑名单确认

`docs/学习记录.md` 和 `docs/开发注意点.md` 是开发过程中的学习笔记和注意事项，可作为背景参考，不是设计依据。

## 硬约束

- **不改动 `llm.py`。** API 调用、stream、retry、provider 兼容这一层保持原样，新代码不直接调 LLM API。
- **不重写 agent 主循环。** `agent.py` 里 `chat()` 的核心结构（问模型 → 判断 tool_calls → 执行 → 继续）保持不变，扩展点集中在工具执行阶段的事件回调和确认机制上，通过模块级事件总线 `events.emit` 打通，而不是改 `_exec_tool` 的调度逻辑。
- **单用户、单 workspace 是 MVP 的前提假设。** `ConfirmRegistry`、事件总线等仍是模块级单例；并行确认通过 `_confirmation_gate` 逐个展示。多 workspace/多用户需要按 `session_id` 隔离，属于后续产品范围。
- **不建独立 Diff 页面，不新增 `workspace_search`/`analyze_project` 之类的工具。** agent 靠 `glob`+`read_file`+`grep` 组合已经够用，专门建工具收益不明确。

## 目录结构

```
corecoder/          agent runtime + FastAPI Web 层（corecoder/web/）
src/                Vue3 + TypeScript 前端源码
docs/               设计文档、开发计划、开发日志与 v2 规划
tests/               pytest 测试
.github/workflows/   CI（pytest + ruff + compileall + 前端类型检查/构建）与发布
README.md / README_CN.md   项目展示用 README，面向 GitHub 访客和技术面试官
```

Web 层代码位于 `corecoder/web/`。Vue 构建产物写入 `corecoder/web/static/dist/`，发布工作流会先构建前端再构建 Python wheel；没有 dist 的源码环境会回退到 `static/index.html`。

## 开发与验证

```bash
pip install -e ".[dev]"
npm ci
npm run type-check
npm run build
python -m pytest tests/ -q      # 跑测试
ruff check corecoder tests      # lint
python -m compileall -q corecoder tests
```

CI 在 Ubuntu/macOS/Windows 上跑 Python 3.10–3.13 测试矩阵，并在 Ubuntu 上验证前端类型与生产构建。提交前应保证以上命令全部通过。

## 与上游 CoreCoder 的关系

`corecoder/` 里未改动的部分（尤其 `llm.py` 的 provider 适配、`context.py` 的三层压缩、`session.py` 的对话历史持久化）应保持上游风格。文件工具只增加 Web workspace 边界，`edit.py`/`write.py`/`bash.py` 增加确认流程；不要借 Web 开发之机重写无关的 Runtime。
