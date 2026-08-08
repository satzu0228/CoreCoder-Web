# CoreCoder-Web

一个本地运行的 Web Coding Agent。它会实时展示执行过程，按工作空间保存对话，并在写文件或执行高风险命令前等待用户确认。

中文文档 · [English](README.md) · [上游 CoreCoder](https://github.com/he-yufeng/CoreCoder)

[![CI](https://github.com/satzu0228/CoreCoder-Web/actions/workflows/ci.yml/badge.svg)](https://github.com/satzu0228/CoreCoder-Web/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB) ![Vue](https://img.shields.io/badge/Vue-3-42b883) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 项目概述

CoreCoder-Web 基于 [CoreCoder](https://github.com/he-yufeng/CoreCoder) Runtime 开发，保留其 LLM 调用、Tool Calling 和多轮执行循环，并扩展了以下能力：

1. **Web 交互与运行管理**：通过 FastAPI 和 SSE 传输模型 token、工具调用、执行结果与确认事件，并提供 workspace 会话持久化、事件续传、任务取消和上下文状态展示。
2. **Human-in-the-loop 工具执行**：在文件写入和高风险命令执行前创建确认点。文件工具先生成 diff，命令工具按 POSIX、PowerShell 和 CMD 规则识别风险；批准后继续执行，拒绝结果返回 Agent 重新决策。

Agent Runtime 负责模型推理和工具调用循环，Web 层负责事件传输与会话状态，确认逻辑位于 Tool 层，因此 CLI 与 Web 可以复用同一套工具接口。

## 已实现功能

以下功能均为 CoreCoder-Web 在 CoreCoder Runtime 基础上新增或改造的部分。

### Web 交互

- Markdown 流式回复，使用 DOMPurify 清洗并限制渲染频率
- 内联执行轨迹，展示工具开始、参数和结果
- Monaco Diff 弹窗，确认写入前查看改动
- 工作空间文件选择器，通过 `@path/to/file` 关联文件
- 上下文用量展示和压缩状态通知

### 对话工作台

- 新建、重命名、搜索、归档、恢复和批量删除对话
- 会话按当前 workspace 隔离，以 JSON 文件持久化
- 轻量 metadata 索引、原子写入、消息数量限制和 Unix 文件权限收紧
- 页面刷新后恢复消息、待确认操作和仍在运行的 SSE 任务
- 同一时间只允许一个 Agent 任务运行，状态包括 `running`、`waiting_confirmation`、`cancelling`、`cancelled`、`interrupted` 和 `error`

### 安全与可靠性

- 服务只绑定 `127.0.0.1`，API 使用启动时生成的随机 token
- Web 文件操作会拒绝 workspace 之外的路径
- 多个确认型工具并行出现时按顺序处理，不会互相覆盖弹窗
- 取消任务会关闭模型流、释放确认等待并终止 Shell 进程树
- 工具执行中断后自动补齐消息历史，避免下一轮模型请求因 tool reply 缺失而失败
- CI 在 Linux、macOS、Windows 上覆盖 Python 3.10–3.13，并执行前端测试、类型检查和生产构建

## 架构

```text
┌─────────────────────────────────────────────────────────────┐
│ Vue 3 + TypeScript                                          │
│ 对话管理 · 执行轨迹 · 人工确认 · Monaco Diff               │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼──────────────────────────────────┐
│ FastAPI Web 层                                               │
│ token 校验 · 事件缓冲/重放 · session API · workspace 边界  │
└───────────────┬──────────────────────────┬──────────────────┘
                │                          │
┌───────────────▼──────────────┐  ┌────────▼──────────────────┐
│ CoreCoder Agent Runtime      │  │ WebSessionManager         │
│ LLM → tool calls → results   │  │ workspace JSON + 索引     │
└───────────────┬──────────────┘  └───────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│ Tool 层                                                      │
│ 路径边界 · diff 审批 · 高风险命令确认                       │
└─────────────────────────────────────────────────────────────┘
```

系统里有两个职责不同的循环：

1. Web 循环启动一次 Agent turn，并把可观察事件传给浏览器，不参与工具选择。
2. Agent 循环调用模型、执行 tool call、追加结果，直到模型返回最终回答。

人工确认放在 Tool 层。写入工具准备好 diff 后发出 `confirm_required`，阻塞在 `threading.Event` 上；确认接口处理对应事件后，工具才继续执行。这样 CLI 与 Web 仍能共用同一套同步工具协议。

## 快速开始

需要 Python 3.10+。如果要修改前端，还需要 Node.js 20+。

```bash
git clone https://github.com/satzu0228/CoreCoder-Web.git
cd CoreCoder-Web

python -m pip install -e ".[dev]"
npm ci
npm run build
```

在项目目录创建 `.env`，也可以设置同名环境变量：

```dotenv
OPENAI_API_KEY=your-api-key
CORECODER_MODEL=gpt-5.5
# OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
```

进入希望 Agent 操作的目录后启动 Web 模式：

```bash
corecoder web
```

程序会选择一个空闲端口，输出带随机 token 的本地地址并打开浏览器。启动命令所在目录就是 workspace 边界。

Web 对话保存在 `~/.corecoder/web-sessions/<workspace-hash>/`。不要提交这个目录，session 文件可能包含提示词、源码片段、diff 和命令输出。

原有 CLI 仍可使用：

```bash
corecoder                         # 交互式 REPL
corecoder -p "解释这个项目"       # 单次任务
corecoder --demo                  # 不需要 API Key 的离线演示
```

如果模型需要通过 LiteLLM 接入：

```bash
python -m pip install -e ".[litellm]"
```

然后设置 `CORECODER_PROVIDER=litellm` 和对应的模型名称。

## 开发与验证

```bash
python -m pytest -q
ruff check corecoder tests
python -m compileall -q corecoder tests

npm run test
npm run type-check
npm run build
```

Vite 会把生产资源写入 `corecoder/web/static/dist/`，Python wheel 会包含这个目录。源码环境没有前端构建时，服务会回退到精简静态页面。

## 当前边界

- 项目面向本地单用户使用，没有按公网服务做安全加固。
- 不同 workspace 的会话互相隔离，但一个进程同一时间只运行一个任务。
- session 保存在本地 JSON 文件中，没有引入数据库。
- 确认请求和实时事件保存在进程内存；历史对话能跨重启恢复，正在执行的任务不会自动续跑。

这些限制让运行时保持轻量，也让副作用容易检查。README 不会把它描述成已经具备多用户和远程部署能力的产品。

## 上游与 License

CoreCoder-Web 是 [he-yufeng/CoreCoder](https://github.com/he-yufeng/CoreCoder) 的二次开发。Agent 主循环、模型适配层、CLI 基础和原始工具抽象来自上游；Web 工作台与可靠性改造在本仓库完成。

项目使用 [MIT License](LICENSE)。
