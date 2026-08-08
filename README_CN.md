# CoreCoder-Web

基于 [CoreCoder](https://github.com/he-yufeng/CoreCoder) 极简 agent runtime 二次开发的 Web 化人机协作编程 agent。

中文 | [English](README.md)

## 项目状态

✅ **MVP 核心闭环和 P0 体验修复已完成。** FastAPI/SSE Web 层、Vue3 前端、工具时间线、虚拟文件树、按需加载的 Monaco Diff，以及 `edit_file`/`write_file`/危险 `bash` 的人工确认均已落地；刷新页面可以恢复当前进程内的对话、工具状态和挂起确认。完整设计与实际变更见 [`docs/MVP 需求文档.md`](<docs/MVP 需求文档.md>)、[`docs/开发日志.md`](<docs/开发日志.md>)。

## 这是什么

本项目基于 [CoreCoder](https://github.com/he-yufeng/CoreCoder) 的 agent runtime（约一千行的极简 coding agent，agent 主循环、LLM 客户端、工具基类原样复用），在其之上新增两件事：

1. **把终端交互循环变成 Web 原生的循环** —— SSE 事件流、workspace 绑定、agent 执行过程的实时可视化，而不只是一问一答的聊天。
2. **在工具执行层嵌入人机协作（human-in-the-loop）执行模型** —— Web 模式下，`edit_file`/`write_file` 先展示 diff，`bash` 命中危险模式时展示命令，用户批准后才真正生效；CLI 保持原有编辑行为。

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
   ├─ Web 路径约束: read_file / grep / glob
   └─ 人工确认:
        ├─ edit_file / write_file  先算 diff → confirm_required → 通过才写入
        └─ bash                    命中危险模式后挂起询问
```

图里其实叠着两层循环，职责边界要分清楚：

- **外层循环（Web 层）** —— 接收输入，调一次 `agent.chat()`，把过程事件转发成 SSE，接收确认。不做任何推理或工具调度的判断。
- **内层循环（Agent Runtime）** —— 调 LLM、判断 tool_call、执行工具、继续推理。完整复用 CoreCoder 原有实现，FastAPI 路由不会伸手进去改这一层的逻辑。

## 人机协作设计

CoreCoder 的工具执行是同步的：`tool.execute()` 返回字符串，循环立刻问模型下一步。要在不改写 agent 主循环的前提下插入"等人确认"这一步，落到三个部件：

- **模块级事件总线**（`events.emit`），作为 `tool_end` / `confirm_required` 的统一出口；`tool_start` 由 `agent.chat()` 的回调进入同一条 SSE 队列。
- **`ConfirmRegistry`** —— 一个加锁的 `event_id → threading.Event` 映射。工具调 `create()`、发出 `confirm_required`，然后阻塞在 `wait()` 上；`POST /api/confirm` 调 `resolve()` 释放它。超时清理和正常返回走的是同一个锁块，内部两本字典不会出现"一本清了、另一本没清"的不一致。
- **单独的拒绝错误路径** —— 用户否决一次修改，既不是参数错误也不是执行失败。这个结果必须能被模型明确识别出来，让它去重新和用户沟通方案，而不是当成报错去盲目重试同一个工具调用。

`EditFileTool` 和 `WriteFileTool` 在写入前生成 diff，确认通过才写文件。多个确认型工具并行出现时会按顺序弹出，避免单个确认框互相覆盖。`BashTool` 只对命中危险模式的命令询问，普通命令（比如 `npm test`）不会被打断。

## 技术栈

| 层 | 选择 |
|---|---|
| Agent runtime | 复用 CoreCoder 主循环；`agent.py` 仅增加工具结束事件，`llm.py` / `context.py` 保持原样 |
| 后端 | FastAPI + Server-Sent Events |
| 前端 | Vue 3 + TypeScript + Naive UI + Monaco Editor |
| 确认状态 | 进程内 `threading.Event`，MVP 阶段限定单用户 / 单 workspace |

## 里程碑

| 阶段 | 交付 |
|---|---|
| M1 | `corecoder web` 启动，浏览器自动打开，SSE token 流式显示 |
| M2 | 文件树 + 工具调用时间线；事件总线与 `tool_end` 在单工具和并行两条路径都打通 |
| M3 | `edit_file` 确认流程 + Monaco diff 展示 |
| M4 | `bash` 确认流程；共用 `request_confirmation()`；刷新页面后挂起的确认状态能恢复 |

## 开发与验证

```bash
pip install -e ".[dev]"
npm ci
npm run type-check
npm run build
python -m pytest tests/ -q
ruff check corecoder tests
```

`corecoder web` 会绑定当前目录作为 workspace。源码仓库未构建 Vue 时会回退到精简前端；CI 和发布流程会先构建 Vue，并把 `static/dist` 打进 wheel。

## License

MIT，继承自上游项目。见 [LICENSE](LICENSE)。
