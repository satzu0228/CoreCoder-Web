# CoreCoder-Web

A local-first Web coding agent with streamed execution traces, workspace-scoped conversations, and approval gates for file writes and risky shell commands.

[中文文档](README_CN.md) · [Upstream CoreCoder](https://github.com/he-yufeng/CoreCoder)

[![CI](https://github.com/satzu0228/CoreCoder-Web/actions/workflows/ci.yml/badge.svg)](https://github.com/satzu0228/CoreCoder-Web/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB) ![Vue](https://img.shields.io/badge/Vue-3-42b883) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> CoreCoder-Web extends CoreCoder's compact Python agent runtime. The runtime still owns model/tool iteration; the Web layer adds durable conversations, event streaming, cancellation, recovery, and human approval at the tool boundary.

## Why this project exists

A coding agent becomes harder to trust once it leaves the terminal. A Web UI must show what the agent is doing, survive refreshes, stop long-running work, and prevent a model from silently writing files or running destructive commands.

CoreCoder-Web implements those controls without moving reasoning into the HTTP layer:

- The browser receives tokens, tool calls, results, status changes, and approval requests over SSE.
- `edit_file` and `write_file` produce a diff and wait for approval before touching disk.
- `bash` runs ordinary commands directly but pauses on high-risk POSIX, PowerShell, and CMD patterns.
- A running task can be cancelled from the UI; active model streams and shell process trees are interrupted.
- Events carry sequence numbers and are buffered for replay after a dropped connection.

## Features

### Coding workflow

- Streaming Markdown replies with DOMPurify sanitization and throttled rendering
- Inline execution trace for tool start/result events
- Monaco diff viewer for file changes
- Workspace file picker with `@path/to/file` references
- Context usage indicator and compression notices
- Seven built-in tools: `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `bash`, and sub-agent delegation

### Conversation workspace

- Create, rename, search, archive, restore, and batch-delete conversations
- JSON persistence scoped to the current workspace
- Lightweight metadata index, atomic writes, message-count limits, and Unix permission hardening
- Refresh recovery for messages, pending approvals, and active SSE runs
- One active agent run at a time, with explicit `running`, `waiting_confirmation`, `cancelling`, `cancelled`, `interrupted`, and `error` states

### Safety and reliability

- The server binds to `127.0.0.1` and protects API routes with a random launch token
- Web file operations reject paths outside the bound workspace
- Approval requests are serialized so concurrent tools cannot overwrite the single confirmation dialog
- Cancellation wakes approval waits, closes model streams, and terminates shell process trees
- Agent history is repaired when a tool round is interrupted, keeping later model requests valid
- CI covers Python 3.10–3.13 on Linux, macOS, and Windows, plus frontend tests, type checking, and production builds

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Vue 3 + TypeScript                                          │
│ conversations · execution trace · approvals · Monaco diff   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼──────────────────────────────────┐
│ FastAPI Web layer                                           │
│ auth token · event buffer/replay · session APIs · workspace │
└───────────────┬──────────────────────────┬──────────────────┘
                │                          │
┌───────────────▼──────────────┐  ┌────────▼──────────────────┐
│ CoreCoder agent runtime      │  │ WebSessionManager         │
│ LLM → tool calls → results   │  │ workspace JSON + index    │
└───────────────┬──────────────┘  └───────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│ Tool layer                                                   │
│ path boundary · diff approval · risky-command confirmation  │
└─────────────────────────────────────────────────────────────┘
```

There are two separate loops:

1. The Web loop starts one agent turn and transports observable events. It does not decide which tool to call.
2. The agent loop talks to the model, executes tool calls, appends results, and continues until the model returns a final answer.

Approval stays inside the tool layer. A write tool prepares its diff, emits `confirm_required`, blocks on a `threading.Event`, and continues only after the matching confirmation endpoint resolves it. The same synchronous tool contract works in both CLI and Web modes.

## Quick start

Requirements: Python 3.10+, Node.js 20+ for frontend development, and an OpenAI-compatible API key.

```bash
git clone https://github.com/satzu0228/CoreCoder-Web.git
cd CoreCoder-Web

python -m pip install -e ".[dev]"
npm ci
npm run build
```

Create a `.env` file or export equivalent environment variables:

```dotenv
OPENAI_API_KEY=your-api-key
CORECODER_MODEL=gpt-5.5
# OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
```

Start the Web workspace from the directory the agent may access:

```bash
corecoder web
```

The command chooses a free localhost port, prints a tokenized URL, and opens it in the default browser. The current directory is the workspace boundary.

Web conversations are stored under `~/.corecoder/web-sessions/<workspace-hash>/`. Do not commit that directory; session files may contain prompts, source excerpts, diffs, and command output.

The original CLI remains available:

```bash
corecoder                         # interactive REPL
corecoder -p "explain this repo"  # one-shot mode
corecoder --demo                  # offline scripted demo
```

For providers that require LiteLLM:

```bash
python -m pip install -e ".[litellm]"
```

Then set `CORECODER_PROVIDER=litellm` and use the provider's model name.

## Development

```bash
python -m pytest -q
ruff check corecoder tests
python -m compileall -q corecoder tests

npm run test
npm run type-check
npm run build
```

Vite writes production assets to `corecoder/web/static/dist/`. The Python wheel includes that directory; a source checkout without a build falls back to a small static page.

## Design constraints

- This is a local, single-user application. It is not hardened for public Internet deployment.
- Conversations from one workspace are isolated from another, but the process intentionally allows only one active run at a time.
- Sessions are stored as local JSON files rather than in a database.
- Approval and live event state are held in process memory; persisted conversation history survives restarts, active work does not resume automatically.

These constraints keep the runtime small and make side effects easy to inspect. They are deliberate boundaries, not deployment claims.

## Upstream and license

CoreCoder-Web is a secondary development of [he-yufeng/CoreCoder](https://github.com/he-yufeng/CoreCoder). The compact agent loop, provider layer, CLI foundations, and original tool abstractions come from upstream; the Web workspace and reliability work live in this repository.

Released under the [MIT License](LICENSE).
