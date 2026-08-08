# CoreCoder-Web

A human-in-the-loop Web coding agent, built by extending [CoreCoder](https://github.com/he-yufeng/CoreCoder)'s minimal agent runtime.

[中文](README_CN.md) | English

## Status

✅ **The v2 conversation workspace is implemented.** The left sidebar now holds workspace-scoped conversation history; the main area uses chat bubbles and an inline agent execution trace. Conversations survive server restarts, SSE and confirmation routes are session-aware, and Monaco diff remains an on-demand modal. See [`docs/v2 优化规划.md`](<docs/v2 优化规划.md>) and [`docs/开发日志.md`](<docs/开发日志.md>).

## What this is

This project builds on [CoreCoder](https://github.com/he-yufeng/CoreCoder)'s agent runtime (a ~1,000-line minimal coding agent — the agent loop, LLM client, and tool base classes are reused as-is) and adds two things on top:

1. **Turning a terminal loop into a Web-native one** — SSE event streaming, workspace binding, real-time visualization of what the agent is doing, not just request/response chat.
2. **A human-in-the-loop execution model in the tool layer** — in Web mode, `edit_file` and `write_file` show a diff before writing, while dangerous `bash` commands pause for approval. CLI edit behavior remains compatible with upstream.

(2) is where the engineering weight is, and where most of the design effort goes.

## Architecture

```
Vue3 + TS + Naive UI + Monaco
            │  SSE
      FastAPI Web Server
            │
   ┌────────┴────────┐
Agent Runtime      WebSessionManager
   │
   ├─ workspace-scoped conversation persistence
   ├─ Web path boundary: read_file / grep / glob
   └─ approval flows:
        ├─ edit_file / write_file — diff → confirm_required → wait → write
        └─ bash                   — dangerous-pattern hit pauses and asks
```

Two loops, kept deliberately separate:

- **Outer loop (Web)** — receive input, call `agent.chat()` once, forward its events as SSE, receive confirmations. No reasoning or tool-dispatch logic lives here.
- **Inner loop (Agent Runtime)** — call the LLM, dispatch tool calls, execute, reason again. Reused as-is from CoreCoder; the FastAPI layer never reaches into it.

## Human-in-the-loop design

CoreCoder's tool execution is synchronous: `tool.execute()` returns a string and the loop immediately asks the model what's next. Inserting a "wait for a human" step into that, without rewriting the agent loop itself, comes down to three pieces:

- **A module-level event bus** (`events.emit`) for `tool_end` and `confirm_required`; the `tool_start` callback enters the same SSE queue.
- **`ConfirmRegistry`** — a locked `event_id → threading.Event` map. A tool calls `create()`, emits `confirm_required`, then blocks on `wait()`; `POST /api/confirm` calls `resolve()` to release it. Timeout cleanup and normal resolution share the same lock, so the internal event/result dicts never drift out of sync.
- **A distinct error path for rejection** — a user declining an edit is neither a parameter error nor an execution failure. It has to read as its own outcome so the model renegotiates the plan instead of blindly retrying the same tool call.

`EditFileTool` and `WriteFileTool` compute a diff before writing. Concurrent approval requests are serialized so the single MVP modal cannot overwrite one request with another. `BashTool` only pauses on dangerous patterns; ordinary commands such as `npm test` run normally.

## Tech stack

| Layer | Choice |
|---|---|
| Agent runtime | CoreCoder loop reused; `agent.py` only adds tool-end events, while `llm.py` and `context.py` remain unchanged |
| Backend | FastAPI + Server-Sent Events |
| Frontend | Vue 3 + TypeScript + Naive UI + Monaco Editor |
| Conversation state | workspace-scoped JSON sessions; one active agent run at a time |
| Confirmation state | in-process `threading.Event`, routed by Web session |

## Roadmap

| Milestone | Deliverable |
|---|---|
| MVP | SSE chat, tool events, edit/write/bash confirmation, lazy Monaco diff |
| v2 M1 | Workspace-scoped conversation storage and session APIs |
| v2 M2 | Conversation sidebar, chat bubbles, and chained agent execution trace |
| v2 M3 | Session-aware chat/confirmation routes, refresh recovery, and single-run lock |
| Next | E2E coverage, connection recovery, Markdown sanitization, and security hardening |

## Development

```bash
pip install -e ".[dev]"
npm ci
npm run type-check
npm run build
python -m pytest tests/ -q
ruff check corecoder tests
```

`corecoder web` binds the current directory as its workspace. A source checkout without a Vue build falls back to the compact frontend; CI and release workflows build Vue and package `static/dist` into the wheel.

## License

MIT, inherited from the upstream project. See [LICENSE](LICENSE).
