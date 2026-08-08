# CoreCoder-Web

A human-in-the-loop Web coding agent, built by extending [CoreCoder](https://github.com/he-yufeng/CoreCoder)'s minimal agent runtime.

[中文](README_CN.md) | English

## Status

✅ **The core MVP loop and P0 experience fixes are complete.** The FastAPI/SSE layer, Vue 3 frontend, virtualized file tree, lazy Monaco diff viewer, and approval flows for `edit_file`, `write_file`, and dangerous `bash` commands are implemented. A refresh restores the current process's conversation, tool states, and pending confirmation. See [`docs/MVP 需求文档.md`](<docs/MVP 需求文档.md>) and [`docs/开发日志.md`](<docs/开发日志.md>).

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
Agent Runtime      Session (in-memory state machine)
   │
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
| Confirmation state | in-process `threading.Event`, single-user / single-workspace scope for the MVP |

## Roadmap

| Milestone | Deliverable |
|---|---|
| M1 | `corecoder web` boots, browser opens, SSE token streaming works |
| M2 | File tree + tool-call timeline; event bus and `tool_end` wired for both the single and parallel tool-execution paths |
| M3 | `edit_file` confirmation flow + Monaco diff viewer |
| M4 | `bash` confirmation flow; shared `request_confirmation()` helper; pending-confirmation state survives a page refresh |

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
