# CoreCoder-Web

A human-in-the-loop Web coding agent, built by extending [CoreCoder](https://github.com/he-yufeng/CoreCoder)'s minimal agent runtime.

[中文](README_CN.md) | English

## Status

🚧 **Design finalized, implementation in progress.** The code in [`corecoder/`](corecoder/) is currently CoreCoder's unmodified engine (agent loop, tool base classes, LLM client, three-tier context compaction). The Web layer, tool-level confirmation flow, and FastAPI/Vue frontend described below are the active build. Full design: [`docs/MVP 需求文档.md`](<docs/MVP 需求文档.md>).

## What this is

This project builds on [CoreCoder](https://github.com/he-yufeng/CoreCoder)'s agent runtime (a ~1,000-line minimal coding agent — the agent loop, LLM client, and tool base classes are reused as-is) and adds two things on top:

1. **Turning a terminal loop into a Web-native one** — SSE event streaming, workspace binding, real-time visualization of what the agent is doing, not just request/response chat.
2. **A human-in-the-loop execution model inside the agent core** — `edit_file` and `bash` stop running silently. They compute a diff or flag a command, pause mid-execution, and wait for explicit user approval before anything actually happens.

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
   ├─ unchanged tools: read_file / write_file / grep / glob
   └─ extended tools (same classes, added a confirmation stage):
        ├─ edit_file  — diff computed → confirm_required event → wait → write
        └─ bash       — blacklist hit pauses and asks, instead of silently rejecting
```

Two loops, kept deliberately separate:

- **Outer loop (Web)** — receive input, call `agent.chat()` once, forward its events as SSE, receive confirmations. No reasoning or tool-dispatch logic lives here.
- **Inner loop (Agent Runtime)** — call the LLM, dispatch tool calls, execute, reason again. Reused as-is from CoreCoder; the FastAPI layer never reaches into it.

## Human-in-the-loop design

CoreCoder's tool execution is synchronous: `tool.execute()` returns a string and the loop immediately asks the model what's next. Inserting a "wait for a human" step into that, without rewriting the agent loop itself, comes down to three pieces:

- **A module-level event bus** (`events.emit`) as the single channel for `tool_start` / `tool_end` / `confirm_required`. `server.py` wires SSE once; every event type flows through the same entry point.
- **`ConfirmRegistry`** — a locked `event_id → threading.Event` map. A tool calls `create()`, emits `confirm_required`, then blocks on `wait()`; `POST /api/confirm` calls `resolve()` to release it. Timeout cleanup and normal resolution share the same lock, so the internal event/result dicts never drift out of sync.
- **A distinct error path for rejection** — a user declining an edit is neither a parameter error nor an execution failure. It has to read as its own outcome so the model renegotiates the plan instead of blindly retrying the same tool call.

`EditFileTool` computes its diff *before* writing and only writes after approval. `BashTool`'s blacklist hit changes from a silent reject to the same pause-and-ask flow — but only for blacklisted commands; ordinary commands (`npm test`) never interrupt the run.

## Tech stack

| Layer | Choice |
|---|---|
| Agent runtime | CoreCoder, unmodified (`agent.py` / `llm.py` / `context.py`) |
| Backend | FastAPI + Server-Sent Events |
| Frontend | Vue 3 + TypeScript + Naive UI + Monaco Editor |
| Confirmation state | in-process `threading.Event`, single-user / single-workspace scope for the MVP |

## Roadmap

| Milestone | Deliverable |
|---|---|
| M1 | `corecoder web` boots, browser opens, SSE token streaming works |
| M2 | File tree + tool-call timeline; event bus and `tool_end` wired for both the single and parallel tool-execution paths |
| M3 | `edit_file` confirmation flow + Monaco diff viewer |
| M4 | `bash` confirmation flow; shared `ConfirmableTool` abstraction extracted from the two real implementations; pending-confirmation state survives a page refresh |

## License

MIT, inherited from the upstream project. See [LICENSE](LICENSE).
