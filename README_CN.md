# CoreCoder-Web

基于 [CoreCoder](https://github.com/he-yufeng/CoreCoder) 极简 agent runtime 二次开发的 Web 化人机协作编程 agent。

中文 | [English](README.md)

## 项目状态

🚧 **设计已定稿，开发进行中。** 当前 [`corecoder/`](corecoder/) 里的代码仍是 CoreCoder 未经改动的原始引擎（agent 主循环、工具基类、LLM 客户端、三层上下文压缩）。下面描述的 Web 层、工具级人机确认机制、FastAPI/Vue 前端是正在推进的开发内容。完整设计见 [`docs/MVP 需求文档.md`](<docs/MVP 需求文档.md>)。

## 这是什么

本项目基于 [CoreCoder](https://github.com/he-yufeng/CoreCoder) 的 agent runtime（约一千行的极简 coding agent，agent 主循环、LLM 客户端、工具基类原样复用），在其之上新增两件事：

1. **把终端交互循环变成 Web 原生的循环** —— SSE 事件流、workspace 绑定、agent 执行过程的实时可视化，而不只是一问一答的聊天。
2. **在 agent 内核里嵌入人机协作（human-in-the-loop）执行模型** —— `edit_file` 和 `bash` 不再悄悄执行。它们先算出 diff 或标记出危险命令，在执行中途挂起，等用户明确批准之后才真正生效。

第 2 点是工程量的重心，也是这个项目大部分设计精力投入的地方。

## 整体架构

```
Vue3 + TS + Naive UI + Monaco
            │  SSE
      FastAPI Web Server
            │
   ┌────────┴────────┐
Agent Runtime      Session（内存态状态机）
   │
   ├─ 原样复用: read_file / write_file / grep / glob
   └─ 改造（同一个类，加一段确认流程）:
        ├─ edit_file  先算 diff → 发 confirm_required 事件 → 等确认 → 通过才写入
        └─ bash       命中黑名单从直接拒绝改为挂起询问
```

图里其实叠着两层循环，职责边界要分清楚：

- **外层循环（Web 层）** —— 接收输入，调一次 `agent.chat()`，把过程事件转发成 SSE，接收确认。不做任何推理或工具调度的判断。
- **内层循环（Agent Runtime）** —— 调 LLM、判断 tool_call、执行工具、继续推理。完整复用 CoreCoder 原有实现，FastAPI 路由不会伸手进去改这一层的逻辑。

## 人机协作设计

CoreCoder 的工具执行是同步的：`tool.execute()` 返回字符串，循环立刻问模型下一步。要在不改写 agent 主循环的前提下插入"等人确认"这一步，落到三个部件：

- **模块级事件总线**（`events.emit`），作为 `tool_start` / `tool_end` / `confirm_required` 的唯一出口。`server.py` 启动时接好一次 SSE，之后所有事件类型都走这一个入口。
- **`ConfirmRegistry`** —— 一个加锁的 `event_id → threading.Event` 映射。工具调 `create()`、发出 `confirm_required`，然后阻塞在 `wait()` 上；`POST /api/confirm` 调 `resolve()` 释放它。超时清理和正常返回走的是同一个锁块，内部两本字典不会出现"一本清了、另一本没清"的不一致。
- **单独的拒绝错误路径** —— 用户否决一次修改，既不是参数错误也不是执行失败。这个结果必须能被模型明确识别出来，让它去重新和用户沟通方案，而不是当成报错去盲目重试同一个工具调用。

`EditFileTool` 在写入之前就把 diff 算好，确认通过才真正写文件。`BashTool` 命中黑名单从直接拒绝改成同一套挂起询问的流程——但只对命中黑名单的命令生效，普通命令（比如 `npm test`）不会打断执行。

## 技术栈

| 层 | 选择 |
|---|---|
| Agent runtime | CoreCoder，未改动（`agent.py` / `llm.py` / `context.py`） |
| 后端 | FastAPI + Server-Sent Events |
| 前端 | Vue 3 + TypeScript + Naive UI + Monaco Editor |
| 确认状态 | 进程内 `threading.Event`，MVP 阶段限定单用户 / 单 workspace |

## 里程碑

| 阶段 | 交付 |
|---|---|
| M1 | `corecoder web` 启动，浏览器自动打开，SSE token 流式显示 |
| M2 | 文件树 + 工具调用时间线；事件总线与 `tool_end` 在单工具和并行两条路径都打通 |
| M3 | `edit_file` 确认流程 + Monaco diff 展示 |
| M4 | `bash` 确认流程；从两个真实实现中提炼出共用的 `ConfirmableTool` 抽象；刷新页面后挂起的确认状态能恢复 |

## License

MIT，继承自上游项目。见 [LICENSE](LICENSE)。
