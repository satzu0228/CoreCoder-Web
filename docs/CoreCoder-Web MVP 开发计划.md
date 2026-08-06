# CoreCoder-Web MVP 开发计划

> 本文档是可执行的开发 TODO，不重复《MVP 需求文档.md》里的背景、前提假设、API 细节设计——涉及具体设计时直接引用该文档章节号。

## 一、现状评估

`corecoder/` 当前与上游 CoreCoder 完全一致，没有任何 Web 相关代码。逐模块评估如下：

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
4. 前端：`ConfirmModal` 组件，收到 `confirm_required` SSE 事件后弹窗展示 diff（先用 `<pre>` 展示纯文本 diff，Monaco Diff Editor 留到阶段 4 再接），用户点击「确认」/「拒绝」调 `/api/confirm`

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

### 阶段 3：`bash` 命令确认闭环

**目标**：把阶段 2 验证过的确认机制在第二个工具上复用一遍，同时验证机制本身是不是真的可复用（而不是只对 edit_file 生效的特例）。

**开发任务**：
1. 改造 `tools/bash.py`：`_check_dangerous()` 命中黑名单后，不再直接 `return "⚠ Blocked"`，改成同一套 `registry.create()` → `emit("confirm_required", {"action": "bash", "command": ...})` → `wait()` 流程
2. 普通命令（未命中黑名单）路径完全不变，不引入任何额外延迟
3. 前端 `ConfirmModal` 扩展：根据 `action` 字段区分展示 diff 还是命令文本
4. 对比 `edit.py` 和 `bash.py` 两份确认逻辑，提炼公共部分——**此时**才提取 `ConfirmableTool` 或一个独立的辅助函数（需求文档 3.2 第三步：抽象基于两个真实实现，不是先验设计）

**涉及模块**：改 `tools/bash.py`、可能新增 `tools/_confirmable.py`（视两份实现重复度决定是否值得抽）

**技术难点**：
- 抽象时机的判断：如果两份代码里"发起确认-等待-处理结果"这段代码几乎一模一样，才值得抽；如果 diff 和命令两种 payload 差异大到共用逻辑很少，就不勉强抽象，写两份也可以接受
- 确认这次改造不会让普通 bash 命令（比如 `npm test`）多出任何等待

**验收标准**：
- 触发一个黑名单命令（比如误导性地让 agent 执行危险命令），网页弹出确认，拒绝后 agent 收到明确拒绝信息
- 触发一个普通命令，全程无确认打断，响应时间和改造前一致
- （如果做了抽象）确认抽象后 `edit_file`、`bash` 两个确认场景行为不变，回归测试通过

---

### 阶段 4：体验补完 — 文件树、Monaco Diff、状态恢复

**目标**：把阶段 0-3 打好的核心闭环包装成可展示的完整产品形态。这一阶段全部是体验优化，没有新的架构风险。

**开发任务**：
1. `corecoder/web/workspace_fs.py`：路径越界校验（`is_relative_to`），供文件树 API 和三个文件工具共用
2. `routes/workspace.py`：`GET /api/tree`、`GET /api/file`
3. 前端补 `FileTree.vue`，Vue3 工程化替换阶段 0 的单文件 HTML
4. `DiffViewer.vue`：Monaco Diff Editor 动态 `import()` 懒加载，接入 `ConfirmModal` 展开
5. `GET /api/session/{id}/pending`：查询当前 `pending_confirm`，支持刷新页面后恢复确认框（需求文档 3.4）

**涉及模块**：新增 `workspace_fs.py`、`routes/workspace.py`、`routes/session.py`，前端从单文件升级为 Vue 工程

**技术难点**：
- 路径越界校验要同时套在文件树 API 和已复用的三个文件工具（`read_file`/`write_file`/`edit_file`）上，避免两处校验逻辑不一致产生安全洞
- Monaco 懒加载不进主 bundle 的验证（打包体积检查）

**验收标准**：
- `../../` 试图跳出 workspace 的路径请求，文件树 API 和文件工具都能正确拒绝
- 点击文件树能预览内容；点开一次 diff 能看到 Monaco 渲染的对比视图
- 刷新浏览器，如果当时有一个待确认的操作，UI 能重新弹出确认框

---

## 三、优先级与阶段映射

**必须完成（MVP，对应上面阶段 0-3）**：
- SSE 流式对话闭环
- 工具调用过程可视化（`tool_start`/`tool_end` 双路径事件）
- `edit_file` 人机确认（diff 预览 + 阻塞等待 + 拒绝语义区分）
- `bash` 危险命令确认
- workspace 路径安全校验（虽然属于阶段 4，但因为文件工具已被复用，这条护栏必须在有任何 Web 请求能触发文件操作之前就位——实际实现顺序上应该在阶段 0 就把 `workspace_fs.py` 的校验函数写好并接入现有三个文件工具，阶段 4 只是补文件树/文件预览这两个新增 API）

**后续优化（v2，不阻塞 MVP 验收）**：
- Monaco Diff Editor 可视化（阶段 2、3 先用纯文本 diff 展示即可验证机制本身）
- 文件树、文件预览 UI
- `ConfirmableTool` 抽象（如果两个工具改造完发现共性不够，可以不抽，两份代码并存也不违反 MVP 目标）
- 会话状态刷新恢复（`GET /api/session/{id}/pending`）
- 多 workspace / 多用户隔离、Session 持久化到数据库、并行工具确认阻塞的调度优化（需求文档已明确列为已知限制，不在 MVP 处理）

**明确不做**：`workspace_search`/`analyze_project` 等新工具、独立 Diff 页面、子 agent 确认链路的特殊处理（复用同一 SSE 通道即可，不需要额外设计）——均已在需求文档中排除。

## 四、开发顺序的现实考量

1. **前置依赖**：事件总线（阶段 1）必须先于确认机制（阶段 2），因为 `confirm_required` 事件复用同一条通道；`ConfirmRegistry`（阶段 2）先于 `bash` 改造（阶段 3），因为阶段 3 直接复用阶段 2 写好的类。
2. **调试难度递增控制**：阶段 0 只验证传输层，阶段 1 只加"只读事件"，阶段 2 才引入"阻塞等待"这个最容易出并发问题的机制，且只在一个工具上验证。如果阶段 2 直接和阶段 3 一起做，出问题时无法判断是机制设计错了还是某个工具的接入方式错了。
3. **快速看到成果**：阶段 0 结束（预计最早可演示的节点）就已经是"CLI agent 变成能跑的网页应用"，阶段 2 结束就是简历里那句"设计模块级事件总线打通 Tool 执行层与 SSE 推送"可以如实写上的节点——不需要等到阶段 4 完工才有东西可看。
4. **简历/面试展示价值排序**：阶段 2（human-in-the-loop 确认机制）> 阶段 1（事件总线设计）> 阶段 3（抽象提炼过程）> 阶段 0/4（工程收尾）。面试官会追问的大概率是"确认卡在哪个线程、超时怎么清理、拒绝和报错怎么区分"，这些都在阶段 2，应该投入最多打磨时间，包括边界情况的手动测试（超时、并发确认、浏览器中途关闭）。

