# CoreCoder-Web MVP 开发计划

> 本文档是 MVP 开发时采用的历史执行计划。阶段 0-5 已完成；实际偏差和 2026-08-08 集成修复以《开发日志.md》为准，不应再把本文件的“现状评估”当作当前仓库状态。

## 一、现状评估

以下是项目启动时的基线评估，不是当前状态：

| 模块 | 现状 | 结论 |
|---|---|---|
| `agent.py` | `chat()` 主循环完整，`on_token`/`on_tool` 回调已存在，单工具/并行工具执行都有 | **直接复用**，仅需补 `tool_end` 事件发射点（2 处，不改循环结构） |
| `llm.py` | provider 适配、流式、重试、成本统计完整 | **直接复用，零改动** |
| `context.py` | 三层压缩完整 | **直接复用，零改动** |
| `config.py` / `prompt.py` | 环境变量配置、系统提示词 | **直接复用，零改动** |
| `tools/read.py` `write.py` `glob_tool.py` `grep.py` `agent.py`(子agent) | 功能完整 | **直接复用，零改动** |
| `tools/base.py` | `Tool` 基类仅有 `execute()`/`schema()` | **直接复用**，不预先设计 `ConfirmableTool`（见需求文档 3.2） |
| `tools/edit.py` | 直接写入后才算 diff，无确认机制 | **需改造**：diff 计算提前到 write 之前 + 接入确认流程 |
| `tools/bash.py` | 命中黑名单直接 `return "⚠ Blocked"` | **需改造**：黑名单命中改为走确认流程，cwd 线程隔离逻辑不动 |
| `session.py` | 对话历史存盘/续聊 | **不动**，与本次新增的运行时状态是两个概念（需求文档 3.4） |
| `cli.py` | REPL / `-p` / `-r` / `--demo` | **需新增** `web` 子命令入口 |
| Web 层（事件总线、ConfirmRegistry、FastAPI、前端） | 不存在 | **全部新增** |

结论：核心引擎零改动或小改动，工作量集中在两处改造（`edit.py`、`bash.py`）+ 全新的 Web 传输层。这与需求文档 0 节的定位一致。

## 二、开发阶段（按功能闭环拆分）

每个阶段结束都应该是一个能跑起来、能演示的状态，不是"这周写完后端下周写前端"。

---

### 阶段 0：打通「输入 → 流式回复」的最短闭环

**目标**：`corecoder web` 能启动、能打开浏览器、能在网页里发一句话看到 agent 逐字流式回复。不涉及工具可视化、不涉及确认，先验证 Web 传输链路本身没问题。

**开发任务**：
1. `corecoder/web/server.py`：`run_web()`，起 uvicorn（绑 `127.0.0.1` + 随机端口）、生成随机 token、`webbrowser.open()`
2. `corecoder/web/app.py`：FastAPI app 注册，创建全局唯一 `Agent` 实例（单 workspace 假设下安全）
3. `corecoder/web/routes/chat.py`：`POST /api/chat`，请求体 `{message}`，内部调 `agent.chat(message, on_token=...)`，`on_token` 把每个 token 包成 SSE `token` 事件推出去
4. `cli.py` 加 `web` 子命令，`-p`/`-r` 不接受（需求文档 1 节）
5. 最简前端：单文件 HTML + `fetch` + `ReadableStream` 手写 SSE 解析（先不上 Vue 工程化），输入框 + 一段纯文本回复区

**涉及模块**：新增 `corecoder/web/`，改 `cli.py` 加子命令入口

**技术难点**：
- SSE 场景下 `EventSource` 不支持 POST body，必须用 `fetch` + `ReadableStream` 手写解析（需求文档 6 节已指出）
- uvicorn 在同步的 `agent.chat()` 阻塞调用下如何不卡住其他请求——MVP 单用户单 workspace 场景下可以接受同步阻塞，用 `run_in_threadpool` 包一层即可，不需要引入 async agent

**验收标准**：
- `corecoder web` 在项目目录执行，浏览器自动打开
- 网页输入一句话，能看到模型逐字流式吐出文本回复
- 关闭终端进程，端口释放，无残留

**为什么放在第一步**：这是风险最高、最容易卡住后续所有工作的链路（SSE 数据格式、端口绑定、浏览器自动打开），越早跑通越好；而且五分钟就能演示"CLI agent 变成网页 agent"，简历/面试展示价值最先兑现。

---

### 阶段 1：工具调用过程可视化（只读工具，不涉及确认）

**目标**：在网页上能看到 agent 读文件、搜索时的实时过程，而不只是等最终答案。这一步只接只读工具（`read_file`/`grep`/`glob`），确认机制留给阶段 2，避免两个新机制一起验证增加排错难度。

**开发任务**：
1. `corecoder/web/events.py`：模块级事件总线，`set_emitter()` / `emit()`（需求文档 3.2 第零步）
2. `agent.py` 补 `tool_end` 发射点：单工具路径和并行路径各一处，都调 `events.emit("tool_end", ...)`（需求文档 3.1）——这是对现有引擎代码**唯一**的改动点，且是新增调用不改变原有控制流
3. `server.py` 启动时 `events.set_emitter(sse_push_fn)`，接到 `/api/chat` 的 SSE 连接上
4. `on_tool` 回调里也调 `events.emit("tool_start", ...)`，让 `tool_start`/`tool_end` 走同一条通道
5. 前端加一个简单的时间线区域：显示「正在调用 xxx」「结果：...」

**涉及模块**：`corecoder/agent.py`（补发射点）、新增 `corecoder/web/events.py`、`server.py` 接线

**技术难点**：
- 并行路径要按每个工具各发一次 `tool_end`，不能等全部 `f.result()` 收集完再一起发（需求文档 3.1 已指出）——用 `concurrent.futures.as_completed` 替代当前 `[f.result() for f in futures]` 的收集方式，逐个到达逐个发
- 验证单工具和并行两条路径的事件都能正确触发，这是需求文档里程碑 M2 明确要求的验证点

**验收标准**：
- 让 agent 读一个文件、搜索一个关键词，网页实时看到「正在读取 xxx.py」「正在搜索 xxx」这类过程提示
- 故意让模型一次触发 2+ 个工具调用（比如"同时读两个文件"），确认两个 `tool_end` 事件都各自及时到达，不是等最慢的那个才一起出现

**为什么是这个顺序**：事件总线是后面确认机制的地基（需求文档 3.2 第零步明确要求先立事件通道），但先只接只读工具能在不涉及"阻塞等待"这种更复杂机制的情况下，把事件总线本身的正确性验证一遍，出问题范围小、好排查。

---

### 阶段 2：`edit_file` 人机协作确认闭环（MVP 核心）

**目标**：这是整个项目技术含量最集中的一步——agent 生成修改方案，网页弹出 diff 确认框，用户点击确认后才真正写入文件。

**开发任务**：
1. `corecoder/web/confirm_registry.py`：`ConfirmRegistry` 类，`create()`/`wait()`/`resolve()`（需求文档 3.2，代码示例可直接照搬）
2. 改造 `tools/edit.py`：
   - 把 `_unified_diff(...)` 调用挪到 `write_text` 之前（需求文档 3.2 第一步指出的关键改动点）
   - 生成 diff 后 `registry.create()` → `events.emit("confirm_required", ...)` → `registry.wait(timeout=300)`
   - `approved=False` 时返回带 `"rejected by user"` 语义的字符串，不进 `except Exception` 分支（需求文档 3.3）
3. `corecoder/web/routes/confirm.py`：`POST /api/confirm`，body `{id, approve}`，调 `registry.resolve()`，`resolve()` 返回 `False`（超时/不存在）时返回明确 4xx
4. 前端：`ConfirmModal` 组件，收到 `confirm_required` SSE 事件后弹窗展示 diff（先用 `<pre>` 展示纯文本 diff，Monaco Diff Editor 留到阶段 5 再接），用户点击「确认」/「拒绝」调 `/api/confirm`

**涉及模块**：新增 `confirm_registry.py`、改 `tools/edit.py`、新增 `routes/confirm.py`

**技术难点**：
- `registry.wait()` 阻塞的是执行 `edit_file` 的那个线程（主线程或线程池 worker），要确认这个阻塞不会拖死 uvicorn 处理其他请求的能力——单工具路径阻塞的是处理 `/api/chat` 请求的线程，`/api/confirm` 走的是另一个请求/线程，两者不冲突
- 前端要在等待确认期间保持 SSE 连接不断开，同时轮询体验要顺畅：`confirm_required` 事件到达后 UI 应该明确进入"等待用户"状态，而不是看起来卡住

**验收标准**：
- 让 agent 修改一处代码，网页在写入前弹出 diff 预览
- 点击「拒绝」：文件不变，agent 收到"用户拒绝"的信息并能合理回应（比如询问用户想怎么改），不是报错重试
- 点击「确认」：文件被正确写入，网页展示最终 diff
- 用 curl 模拟一个不存在的 `confirm_id` 调 `/api/confirm`，返回明确的 4xx 而不是 500 或静默成功

**为什么是核心且必须做**：这是需求文档反复强调的"区别于随便包一层 UI"的技术含量所在。没有这一步，项目退化成普通的 chat-over-agent 演示。

---

### 阶段 3：前端框架迁移 — 从原生 HTML 到 Vue3 工程化

**目标**：在阶段 2 完成后立即做前端框架迁移，避免阶段 5 时 ConfirmModal/工具卡片等 UI 模块已散布在原生 JS 中，后期难以重构。这一步把已有的功能用 Vue3 + TypeScript 重新组织，不添加新功能。

**开发任务**：
1. 初始化前端项目：`src/` 目录、Vite + Vue3 + TypeScript 工程化（不用 CSS 框架，保持简洁）
2. 按模块分离 Vue 组件：
   - `ChatPanel.vue` — 消息输入框、对话区域
   - `ToolCallCard.vue` — 工具执行卡片（黄/绿 running/done 状态）
   - `ConfirmModal.vue` — 确认弹窗（edit/bash 两种模式）
3. 状态管理：使用 Pinia 管理 session 和事件流（简单 store，避免过度设计）
4. SSE 连接处理：封装 `useAgentStream` composable，复用阶段 0-2 的 SSE 解析逻辑
5. 打包配置：Vite build 输出到 `corecoder/web/static/dist/`，FastAPI 改为从这里加载前端

**涉及模块**：新增 `src/` 前端工程目录、改 `web/server.py`/`app.py` 指向打包后的静态文件

**技术难点**：
- 确保 SSE 流式处理逻辑从原生 JS 平滑迁移到 Vue 生命周期（mounted、unmounted 时接空连接）
- Pinia store 的设计要简洁，避免状态分散（消息列表、待确认事件 ID、token 都放一个 store）
- 打包时要确保生成的 `index.html` 还能读 URL query 参数里的 `token`

**验收标准**：
- `npm run build` 后 `corecoder web` 启动，浏览器自动打开能看到 Vue 版界面
- 功能完全等效于阶段 2 的原生 HTML 版：
  - SSE 流式文本正常显示
  - tool_start/tool_end 卡片动画正常（running → done）
  - ConfirmModal 弹窗、Approve/Reject 按钮工作
  - token 校验、403 错误处理正常
- 代码组织清晰，后续添加文件树/Monaco diff 只需要引入新组件，不需要改现有逻辑

**为什么要在阶段 3 做而不是最后**：原生 HTML 版已在阶段 0-2 里达到功能完整度，此时迁移框架是最好时机——功能稳定、无新增特性干扰、后续 bash 确认（阶段 4）和文件树（阶段 5）的 UI 都能直接用 Vue 写，不用再改原生 JS。如果拖到最后，会面临"要么在原生 JS 里继续加 bash UI 逻辑导致散乱，要么迁移后再加新功能导致测试复杂"的两难。

---

### 阶段 4：`bash` 命令确认闭环

**目标**：把阶段 2 验证过的确认机制在第二个工具上复用一遍，同时验证机制本身是不是真的可复用（而不是只对 edit_file 生效的特例）。此时前端已是 Vue 组件，bash 的 ConfirmModal 集成更清晰。

**开发任务**：
1. 改造 `tools/bash.py`：`_check_dangerous()` 命中黑名单后，不再直接 `return "⚠ Blocked"`，改成同一套 `registry.create()` → `emit("confirm_required", {"action": "bash", "command": ...})` → `wait()` 流程
2. 普通命令（未命中黑名单）路径完全不变，不引入任何额外延迟
3. 前端 `ConfirmModal.vue` 扩展：根据 `action` 字段区分展示 diff 还是命令文本（已有框架，只需扩展 props 和 UI 逻辑）
4. 新建 `web/_confirmable.py`：提炼 `request_confirmation()` 通用函数，`edit.py` 和 `bash.py` 都调用它
5. 编写回归测试：dangerous command confirm / normal command direct execute / edit_file confirmation regression

**涉及模块**：改 `tools/bash.py`、新增 `web/_confirmable.py`、改 `ConfirmModal.vue`

**技术难点**：
- `registry.wait()` 返回三态（APPROVED/REJECTED/TIMEOUT），edit.py 和 bash.py 都要正确处理
- 确认这次改造不会让普通 bash 命令多出任何等待
- Vue 组件单元测试中模拟 SSE 事件流

**验收标准**：
- 触发一个黑名单命令，网页弹出确认，拒绝后 agent 收到明确拒绝信息
- 触发一个普通命令，全程无确认打断，响应时间和改造前一致
- 编辑和命令确认两种场景都能正常工作，回归测试通过

---

### 阶段 5：体验补完 — 文件树、Monaco Diff、状态恢复

**目标**：把阶段 0-4 打好的核心闭环包装成可展示的完整产品形态。此时前端已是 Vue 工程，添加文件树和 Monaco 集成相对简洁。

**开发任务**：
1. `corecoder/web/workspace_fs.py`：路径越界校验（`is_relative_to`），供文件树 API 和三个文件工具共用
2. `routes/workspace.py`：`GET /api/tree`、`GET /api/file`
3. 前端补 `FileTree.vue` 和 `DiffViewer.vue`：
   - `FileTree.vue` 显示文件树，点击打开文件预览
   - `DiffViewer.vue` 集成 Monaco Diff Editor，由 `ConfirmModal` 触发展开
4. `GET /api/session/pending`：查询当前 pending confirmation，支持刷新页面后恢复确认框（需求文档 3.4）

**涉及模块**：新增 `workspace_fs.py`、`routes/workspace.py`、`routes/session.py`、新增前端组件 `FileTree.vue`/`DiffViewer.vue`

**技术难点**：
- 路径越界校验要同时套在文件树 API 和三个文件工具上，避免安全洞
- Monaco Diff Editor 的动态加载和懒加载（不进主 bundle）
- 页面刷新后恢复待确认状态（从 localStorage 或服务端查询）

**验收标准**：
- `../../` 试图跳出 workspace 的路径请求被正确拒绝
- 点击文件树能预览内容；点开一次 diff 能看到 Monaco 渲染的对比视图
- 刷新浏览器，如果有待确认的操作，UI 能重新弹出确认框

---

## 三、优先级与阶段映射

**必须完成（MVP，对应上面阶段 0-4）**：
- SSE 流式对话闭环（阶段 0）
- 工具调用过程可视化（阶段 1）：`tool_start`/`tool_end` 双路径事件
- `edit_file` 人机确认（阶段 2）：diff 预览 + 阻塞等待 + 拒绝语义区分
- 前端框架迁移（阶段 3）：从原生 HTML 到 Vue3 工程化，功能等效但代码组织清晰
- `bash` 危险命令确认（阶段 4）：黑名单确认 + 三态返回值 + 通用函数提炼
- workspace 路径安全校验（阶段 5，但实现顺序在阶段 4 之后补充在 bash.py 改造里）

**后续优化（v2，不阻塞 MVP 验收）**：
- 会话状态刷新恢复（`GET /api/session/pending`）——阶段 5 完整版，MVP 可选
- 多 workspace / 多用户隔离、Session 持久化到数据库、并行工具确认阻塞的调度优化（需求文档已明确列为已知限制，不在 MVP 处理）

**明确不做**：`workspace_search`/`analyze_project` 等新工具、独立 Diff 页面、子 agent 确认链路的特殊处理（复用同一 SSE 通道即可，不需要额外设计）——均已在需求文档中排除。

## 四、开发顺序的现实考量

1. **前置依赖**：
   - 事件总线（阶段 1）必须先于确认机制（阶段 2）
   - `ConfirmRegistry`（阶段 2）先于 `bash` 改造（阶段 4）
   - 阶段 2 完成后立即做前端框架迁移（阶段 3），避免原生 JS 逻辑散乱

2. **调试难度递增控制**：阶段 0 只验证传输层 → 阶段 1 只加"只读事件" → 阶段 2 引入"阻塞等待" → 阶段 3 框架迁移保证功能等效 → 阶段 4 在 Vue 框架内添加新确认类型。出问题时范围逐步确定。

3. **快速看到成果**：
   - 阶段 0 结束：Web 版 agent
   - 阶段 2 结束：人机协作确认机制（核心创新）
   - 阶段 3 结束：专业前端工程（便于继续开发）
   - 阶段 4 结束：完整的工具确认生态
   - 不需要等到阶段 5 完工才有东西可看

4. **简历/面试展示价值排序**：
   - 阶段 2（human-in-the-loop 确认机制）— 最有技术深度
   - 阶段 1（事件总线设计）— 架构设计亮点
   - 阶段 3（框架迁移）— 工程能力
   - 阶段 4（抽象提炼）— 代码复用设计
   - 阶段 0/5（工程收尾）

5. **框架迁移的时机**：在阶段 2 完成后、阶段 4 开始前做迁移，而非拖到最后，原因：
   - 功能已稳定，迁移时无需同时调试新功能
   - 后续 bash 确认的 UI 可直接用 Vue 组件写，代码更清晰
   - 阶段 5 的文件树、Monaco diff 都基于 Vue 框架，集成更简单
   - 如果拖到最后，面临"要么在原生 JS 里继续堆砌导致混乱，要么迁移后从零开始写"的困境
