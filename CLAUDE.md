# CLAUDE.md

本文件面向参与 CoreCoder-Web 开发的代码 Agent 和开发者。项目说明与使用方式见 [README_CN.md](README_CN.md)。

## 项目定位

CoreCoder-Web 基于 [CoreCoder](https://github.com/he-yufeng/CoreCoder) 的轻量 Agent Runtime，增加了本地 Web 工作台和 Human-in-the-loop 工具审批。

Runtime 负责模型调用、tool call 调度和上下文管理。FastAPI 层负责会话、SSE、取消恢复和 workspace API；Vue 前端展示对话、执行轨迹、确认弹窗和 Monaco Diff。

## 当前状态

MVP、v2 和 v3 已完成。当前代码包含：

- workspace 级多会话持久化、搜索、归档和批量删除；
- token、工具事件、状态、上下文信息的 SSE 传输；
- 事件序号、缓冲和断线重放；
- 模型流、确认等待和 Bash 进程树取消；
- Markdown 清洗与流式渲染节流；
- edit/write diff 审批和跨平台危险命令确认；
- Python 测试、Vitest、TypeScript 类型检查与多平台 CI。

判断行为时以代码和测试为准。本地开发笔记不属于发布内容，也不是当前待办列表。

## 设计边界

- 应用只绑定 `127.0.0.1`，按本地单用户工具设计，不作为公网多租户服务运行。
- `corecoder web` 的启动目录是 workspace 边界，Web 文件 API 和文件工具不能越界。
- 一个进程同一时间只允许一个 Agent run。不要只移除运行锁就宣称支持并发。
- Human-in-the-loop 位于 Tool 层。路由只解析和转发确认结果，不在 HTTP 层复制工具业务逻辑。
- Agent 主循环仍保持“模型 → tool calls → 工具结果 → 继续模型”的结构。新增能力应优先使用明确的回调、事件或上下文，而不是在路由中绕过 Runtime。
- LLM 层可以处理流取消和 provider 兼容，但 Web 路由不能直接调用模型 API。
- 用户拒绝确认是业务结果，不是参数错误或工具异常。模型需要收到明确结果后重新选择方案。
- 现有工具集合已经覆盖项目读写与检索。新增工具前先判断能否由 `glob`、`grep`、`read_file` 等组合完成。

## 目录

```text
corecoder/                    Python Agent Runtime 与 CLI
corecoder/web/                FastAPI、session、SSE、确认和 workspace API
corecoder/web/static/dist/    Vue 生产构建产物
src/                          Vue 3 + TypeScript 前端
tests/                        pytest 与 Vitest 测试
.github/workflows/            CI 与 PyPI 发布流程
```

## 修改时要注意

- `WebSessionManager` 的 metadata 索引是缓存，正式 session JSON 才是持久化数据源。
- Assistant 的 tool call 与对应 tool reply 必须成对；取消或异常不能留下损坏的消息历史。
- SSE 新事件应带 session 与 sequence，并同时考虑首次连接、重连重放和全量 resync。
- 前端不能在每个 token 上重新解析整段长 Markdown，也不能在用户向上阅读时强制滚动到底部。
- 写文件、删除、归档等操作要保留运行态冲突检查。路径相关逻辑必须使用解析后的 workspace 边界。
- 不要提交 `.env`、本地 session、测试截图或临时服务脚本。

## 验证

```bash
python -m pytest -q
ruff check corecoder tests
python -m compileall -q corecoder tests

npm run test
npm run type-check
npm run build
```

CI 在 Ubuntu、macOS、Windows 上测试 Python 3.10–3.13；前端 job 使用 Node.js 20。发布前会先构建 Vue，再把 `corecoder/web/static/dist/` 打入 Python wheel。

## 上游关系

仓库保留 CoreCoder 的 Agent/CLI 基础，同时对 `agent.py`、`llm.py`、`context.py` 和工具层做了 Web 可靠性扩展。修改这些文件时要区分“上游 Runtime 行为”和“CoreCoder-Web 新增能力”，不要为了前端需求重写无关的 provider 或上下文逻辑。
