# 基于 CoreCoder 二次开发 Web Coding Agent — MVP 需求文档（精简版）

## 0. 项目定位

这不是给 CoreCoder 套一个网页壳，而是在 CoreCoder Runtime 基础上做**两件事**：

1. 把终端交互产品化为 Web 交互（workspace 绑定、SSE 流式、可视化）
2. 扩展 Agent 的工具层与执行模型，加入**人机协作（human-in-the-loop）确认机制**

第二点是这个项目真正的技术含量所在，也是区别于"随便找个开源 agent 包一层 UI"的地方。MVP 的一切取舍都以此为优先级：**能体现 agent 工程能力的部分优先做深，纯展示性的部分优先做薄**。

**两个贯穿全文的前提假设，先在这里显式写清楚，后面各节不再重复：**

- **单用户、单 workspace。** `corecoder web` 绑定的是启动时所在目录这一个 workspace，进程内同一时间只服务一个使用者。这意味着后面出现的模块级单例（比如 `ConfirmRegistry`、事件总线）在 MVP 阶段是安全的——不是因为设计上做了隔离，而是因为根本不存在"多个 workspace/多个用户共享同一个进程状态"这个场景。如果以后要支持多 workspace 或多用户，`ConfirmRegistry`、bash 的 `cwd`、事件总线这些目前的全局单例都需要改成按 `session_id`/`workspace_id` 隔离，这是 v2 要处理的问题，MVP 阶段不做。
- **LLM 调用层不改动。** CoreCoder 原有的 `llm.py`（API 调用、stream、retry、provider 兼容）保持不变，`agent.py` 和新增的 FastAPI 路由都不直接调用 LLM API，继续通过 `llm.py` 这一层。0 节说的"两件事"里都不包含这部分。

------

## 1. 目标效果

```bash
cd my-project
corecoder web
```

执行后：获取当前目录 → 绑定为 workspace → 启动 FastAPI（127.0.0.1，随机端口）→ 自动打开浏览器。

用户在网页里对话，agent 读代码、搜索、**提出修改方案等待确认**、**执行命令等待确认**，全过程通过 SSE 实时可视化；确认通过后才真正写入文件，并在界面上展开 diff。

`corecoder web` 与现有 CLI 参数的关系：CLI 原有 `-p`（一次性执行）、`-r`（恢复会话）、`--demo` 这几个参数是为终端交互设计的，MVP 阶段 `web` 子命令**不接受 `-p` 和 `-r`**——`-p` 语义上和"网页里持续对话"冲突，`-r` 涉及把历史 `messages` 灌回一个新启动的 Web Session，属于 v2 再考虑的范围。`corecoder web` 目前只做"绑定当前目录 workspace + 全新会话"这一条路径。

------

## 2. 整体架构

```
Vue3 + TS + Naive UI + Monaco
            │
           SSE
            │
      FastAPI Web Server
            │
   ┌────────┴────────┐
   │                 │
Agent Runtime    Session（内存态状态机）
   │
   ├─ 复用原生工具: read_file / write_file / grep / glob
   └─ 改造原生工具（不新增工具类，直接在原实现上加确认流程）:
        ├─ edit_file  引入 Human-in-the-loop 审批：先算 diff → 确认 → 通过才 write
        └─ bash       危险命令处理从"直接拒绝"改为"询问用户"
```

**不做**：`workspace_search`、`analyze_project` 这类独立新工具（agent 本来就能用 `glob`+`read_file`+`grep` 组合完成，专门建工具收益不明确，MVP 阶段砍掉，作为 v2 方向保留）；不做独立 Diff 页面；不做多 workspace / session 持久化到数据库。

这张图其实是两层循环的叠加，写代码时要分清楚各自的职责边界，不要混在一起：

- **外层循环（Web 交互层，FastAPI + Vue）**：只负责"接收用户输入 → 调一次 `agent.chat()` → 把过程和结果通过 SSE 展示出去 → 接收确认"，本身不做任何推理或工具执行的决策。CLI 版本里这层是 `while True: 用户输入 → agent.chat() → 打印结果`，Web 版把它换成 `POST /api/chat` 收消息、SSE 推事件，逻辑角色不变，只是接口形态变了。
- **内层循环（Agent Runtime）**：负责"调 LLM → 判断 tool_call → 执行工具 → 继续推理"这一整套，就是 `agent.chat()` 内部的循环。这部分完全复用 CoreCoder 原有实现，**不要把这层逻辑塞进 FastAPI 路由里**——路由函数应该只是薄薄一层，调用 `agent.chat()` 并把它产生的事件转发成 SSE，本身不应该出现任何"判断要不要调下一个工具"这类属于内层循环的逻辑。

------

## 3. Agent 内核改造（本项目核心，重点打磨）

### 3.1 执行模型问题：确认到底是"阻塞"还是"分两轮"

CoreCoder 的 `agent.py` 里工具调用是同步的：`tool.execute(**kwargs)` 返回字符串后立刻写回 `messages`，循环立即问模型下一步。要在这套同步模型里插入"等人确认"这一步，有两种做法：

| 方案                          | 做法                                                         | 取舍                                                         |
| ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| A. 分两轮对话                 | `execute()` 直接返回"已提交待确认"，确认结果由用户下一次消息触发新逻辑 | 需要在 `agent.chat()` 之外单独维护一套状态机，和现有对话流分离，改动面大 |
| **B. 单次调用内阻塞（采用）** | `execute()` 内部生成方案后，通过 `threading.Event().wait()` 挂起当前线程，SSE 先推 `confirm_required` 事件告知前端；`/api/confirm` 请求到达后 `set()` 该 event，`execute()` 读取用户选择，决定放行或中止 | 尽量不修改 `agent.py` 的主循环（for 轮次、`_exec_tool` 调度逻辑保持不变），扩展点集中在 Tool 执行阶段的事件回调与确认机制；跟 `bash.py` 原有的危险命令拦截是同一种思路的延伸，可以统一抽象 |

**采用方案 B**，理由：改动面小、和现有代码风格一致、不需要额外的跨请求状态机。

**需要先补一个缺口：`tool_end` 目前没有触发点，而且它和 `confirm_required` 的触发机制必须统一，不能是两条路。** 当前 `agent.chat()` 里单工具执行路径是：

```python
if on_tool:
    on_tool(tc.name, tc.arguments)   # → Web 版对应 tool_start
result = self._exec_tool(tc)         # → 执行工具
self.messages.append(...)            # → 结果写回消息列表，流程到此为止
```

`on_tool` 回调对应 `tool_start`，但 `_exec_tool` 返回之后、`messages.append` 之前没有任何 hook，`tool_end` 事件在现有代码流里无处安放。

这里有两条路可选：要么给 `_exec_tool`/`execute()` 加一个 `on_event` 回调参数一路传进 Tool 内部；要么让 `tool_start`/`tool_end`/`confirm_required` 都走 3.2 节要建的模块级事件总线 `events.emit`。**采用后者**——`confirm_required` 必须由 `EditFileTool`/`BashTool` 内部发起（只有 Tool 自己知道 diff 算完、可以弹确认框的时机），这一步没法用外层回调表达，所以事件总线这条通道本来就要建；而 `tool_start`/`tool_end` 的信息（工具名、参数、结果）`agent.chat()` 自己就拿得到，不需要额外从 Tool 内部传出来。让两者统一走同一个 `events.emit`，而不是一半走回调注入、一半走事件总线，`server.py` 只需要在启动时 `events.set_emitter(sse_push_fn)` 接好一次，之后所有事件类型都从这一个入口出去：

```python
# agent.py 单工具路径
result = self._exec_tool(tc)
events.emit("tool_end", {"id": tc.id, "result": result})   # 和 EditFileTool 内部发 confirm_required 用同一条通道
self.messages.append(...)
```

并行路径同样要处理，而且要按每个工具各发一次，不能等 `f.result()` 全部收集完再一起发（那样就失去了"实时"的意义）：

```python
# agent.py 并行路径
results = self._exec_tools_parallel(resp.tool_calls, on_tool)
for tc, result in zip(resp.tool_calls, results):
    events.emit("tool_end", {"id": tc.id, "result": result})
    self.messages.append(...)
```

`on_tool`（`tool_start`）保留原有的回调注入方式不变——它在工具执行前触发，`agent.chat()` 本来就是唯一知道"要开始执行哪个工具"的地方，不需要改。

### 3.2 开发顺序：先在具体工具里写死，稳定后再抽象

源码里 `tools/base.py` 的 `Tool` 基类非常简单，只有 `execute()`/`schema()`，没有 lifecycle hook、没有事件机制。**不要一上来就设计 `ConfirmableTool` 抽象基类**——两个确认场景（edit / bash）目前具体需要传递什么 payload、`Event` 生命周期怎么管理都还没跑通过一次，过早抽象容易抽错。正确顺序：

**第零步（前置，必须先做）：把事件通道立起来**

`Tool.execute()` 当前的签名是纯函数式的——只接收参数，只返回字符串，没有任何 I/O 通道能让它主动往外推事件，也不知道 SSE 连接在哪、谁在消费。这不是实现细节，是要先决定清楚的架构点，否则写到 `edit.py` 里调 `_emit_sse` 的时候会发现根本调不到。MVP 采用最简单的方案：**模块级的事件总线单例**，和后面 `_pending_confirms` 的全局字典是同一种风格，`server.py` 启动时注入真正的 SSE 推送函数：

```python
# events.py
_sse_emit = None

def set_emitter(fn):
    global _sse_emit
    _sse_emit = fn

def emit(event_type: str, data: dict):
    if _sse_emit:
        _sse_emit(event_type, data)
```

同时把确认场景里反复要用到的 `event_id / threading.Event / 结果字典` 这一组状态，从一开始就包一层薄封装，而不是让 `edit.py` 和 `bash.py` 各自维护两本裸字典——这不是"过早抽象"，因为这层封装不涉及 edit/bash 各自的业务逻辑，只是给读写加锁 + 统一清理，本身就是通用基础设施：

```python
# confirm_registry.py
import threading

class ConfirmRegistry:
    def __init__(self):
        self._events: dict[str, threading.Event] = {}
        self._results: dict[str, bool] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        event_id = uuid4().hex
        with self._lock:
            self._events[event_id] = threading.Event()
        return event_id

    def wait(self, event_id: str, timeout: float = 300) -> bool:
        with self._lock:
            ev = self._events[event_id]
        ev.wait(timeout=timeout)          # 不能放锁内：resolve() 需要拿锁才能 set()，放锁内会死锁
        with self._lock:
            approved = self._results.pop(event_id, False)
            self._events.pop(event_id, None)   # 无论超时与否都清理，避免两本字典状态不一致
        return approved

    def resolve(self, event_id: str, approve: bool) -> bool:
        with self._lock:
            if event_id not in self._events:
                return False   # 已超时或不存在，/api/confirm 应返回明确错误而非静默吞掉
            self._results[event_id] = approve
            self._events[event_id].set()
        return True

registry = ConfirmRegistry()
```

这个封装顺带解决了两个原本会在 edit.py/bash.py 里各埋一次的问题：`wait()` 里无论是正常收到结果还是等到超时，都会在同一个 `with self._lock` 块里把 `_events`/`_results` 一起清理掉，不会出现"一本字典清了、另一本还留着"的不一致；`resolve()` 对已经不在 `_events` 里的 `event_id`（超时后才到达的 `/api/confirm` 请求）直接返回 `False`，路由层可以据此给前端一个明确的错误而不是静默吞掉，读写也都在锁内完成，不存在 `wait()` 和 `resolve()` 并发写同一个 key 的竞态窗口。

**第一步：直接在 `EditFileTool` 里写确认逻辑（不建新类）**

```python
# tools/edit.py（在现有 EditFileTool 基础上改）
def execute(self, file_path, old_string, new_string):
    ...
    new_content = content.replace(old_string, new_string, 1)
    diff = _unified_diff(content, new_content, str(p))   # 关键：diff 要在 write 之前算好并发出去

    event_id = registry.create()
    events.emit("confirm_required", {"id": event_id, "action": "edit_file",
                                      "file_path": file_path, "diff": diff})
    approved = registry.wait(event_id, timeout=300)
    if not approved:
        return f"Edit rejected by user.\n{diff}"

    p.write_text(new_content, encoding="utf-8")           # 确认通过才真正写入
    _changed_files.add(str(p))
    return f"Edited {file_path}\n{diff}"
```

`tool_end` 不在这里发——按上面 3.1 节的统一设计，`tool_end` 由 `agent.chat()` 在 `_exec_tool` 返回后统一调 `events.emit`，`EditFileTool.execute()` 内部只负责 `confirm_required` 这一个事件，返回值仍然是字符串，和其他工具保持同样的调用约定。

关于"diff 要在 write 之前算好"这一点，现有源码（edit.py 第 68-73 行）的准确情况是：`_unified_diff(content, new_content, ...)` 这行函数调用确实写在 `write_text` 之后，但它的两个输入参数 `content`（旧内容）和 `new_content`（替换后的内容）在写入之前就已经算好了——严格说不是"diff 数据算错了"，而是"diff 这个函数调用的时机不对"：如果 `write_text` 抛异常，`_unified_diff` 根本不会被执行到，确认框也就拿不到 diff。要改的是把 `_unified_diff(...)` 这行调用挪到 `write_text` 之前执行，让 diff 在任何写入动作发生前就已经生成并可以发给前端。

**第二步：改 `bash.py`**，同样的模式写一遍（`registry.create()` → `events.emit("confirm_required", ...)` → `registry.wait()` → 读结果决定放行/拒绝）。

**第三步：两处都跑通之后**，对比两份代码，把重复的确认发起 / 等待 / 收尾逻辑提炼成 `ConfirmableTool` 基类或一个独立的工具函数（`ConfirmRegistry` 本身已经在第零步抽出来了，这一步提炼的是"围绕 registry 的调用顺序"这层业务逻辑）。抽象基于两个真实实现的共性提炼，不是先验设计。

`bash.py` 里原来命中黑名单就直接 `return f"⚠ Blocked: ..."` 的逻辑，改成走上面这套确认流程，从"直接拒绝"变成"询问用户"——**只对命中黑名单的命令弹确认框，普通命令（如 `npm test`）不打断执行**，避免每条命令都要人工点一下导致 agent 卡顿。

**顺带修一个容易被忽略的点：`cwd` 不要用全局变量。** 如果 `bash.py` 沿用 CoreCoder CLI 版本里"进程当前目录即 workspace"的假设（比如 `cwd = os.getcwd()` 这种写法固化成模块级变量），在本节开头的"单用户单 workspace"前提下暂时不会出错，但这是一个容易在 v2 支持多 workspace 时被忘掉、进而互相污染的隐患。MVP 阶段就应该让 `BashTool.execute()` 从 workspace 绑定的上下文里取 `cwd`（而不是读一个全局变量），哪怕现在这个上下文里只有一个 workspace，这样以后要按 session 隔离时，改动只在"上下文从哪来"这一处，不用回头排查 `bash.py` 内部有没有偷用全局状态。

**已知限制（MVP 阶段不解决，显式记录）：**

- **并行工具调用会被确认阻塞拖慢。** 当模型一次返回多个 `tool_calls`（比如同时调用 `edit_file` 和 `bash`）时，`_exec_tools_parallel` 用线程池并发执行，但用 `f.result()` 按顺序收集结果。如果 `edit_file` 在 `registry.wait()` 里挂起，即使 `bash` 那个线程已经跑完，主线程仍然卡在等 `edit_file` 的 future 上，导致 `bash` 的 `tool_end` 发不出去，前端看起来 `bash` 还在转圈。这不是死锁，只是体验上有延迟。MVP 阶段不改 `_exec_tools_parallel` 的调度顺序（拆分"需确认"和"不需确认"两批分别回报是合理的 v2 优化，但 MVP 阶段引入"部分结果先返回"会和 3.2 节"先写死、稳定后再抽象"的开发顺序原则冲突），只在文档里显式记录这个已知限制。
- **子 Agent（`AgentTool`）复用同一条确认通道。** 如果子 agent 内部也触发了 `edit_file` 确认，它调用的仍是同一个模块级 `events.emit`，事件会推到同一条 SSE 连接——这是期望行为，不需要额外设计；但子 agent 确认期间父 agent 的执行会一并暂停，这一点在 M2/M3 之间要显式提一句，避免遗漏。
- **浏览器关闭后阻塞线程的回收依赖超时。** 用户关闭浏览器后，`registry.wait()` 仍在等，300 秒超时后才返回 `Edit rejected` 并释放线程池 worker。MVP 单用户场景下这个占用可以接受，暂不做主动的连接断开检测。

### 3.3 错误分类：拒绝确认不是"异常"，不能走 `except Exception` 那条路

CoreCoder 原有的错误处理是分类的：**参数错误**（比如工具调用缺 `file_path`）告诉模型"参数重新生成"，**执行错误**（比如文件不存在）告诉模型"这次执行失败了"，而不是用一个 `except Exception` 把所有情况都拍扁成同一句话——分类的意义在于，模型看到不同类型的失败，后续应该采取不同的行动（改参数 vs 换个思路），拍扁了模型就没法自我修正。

Web 版新增的"用户拒绝确认"是**第三类结果**，既不是参数错误，也不是执行错误，不能简单套进现有两类里：

- `EditFileTool`/`BashTool` 里 `registry.wait()` 返回 `False` 时，返回值（比如 `"Edit rejected by user.\n{diff}"`）要让模型能明确识别出"这不是失败，是用户主动否决了这个方案"，而不是被当成工具执行报错去重试同样的操作。措辞上要体现出"user_rejected"这个语义，而不是简单复用报错的模板。
- 超时未响应（`registry.wait()` 等满 300 秒仍未 `resolve`）在返回给模型时也要和"用户明确拒绝"区分开——超时更接近"当前无法确认，先跳过"，模型收到后合理的反应可能是询问用户接下来想怎么做，而不是当成方案被否决直接换一个方案重试。
- 这两种情况都不应该经过 CoreCoder 原有的"工具执行错误"分支，因为那条分支语义上对应的是"工具本身跑挂了"，会让模型误判成需要修 bug 或换参数重试，而实际上问题出在"人没有批准"，模型该做的是重新和用户沟通方案，而不是自己想办法绕过去。

MVP 阶段不需要为此新增复杂的错误类型系统，只要在 `EditFileTool`/`BashTool` 返回给模型的字符串里把"用户拒绝"和"超时未确认"这两种情况的措辞和现有的"执行报错"区分开，模型就有足够信息做出合理反应。

### 3.4 Session 状态：区分「原有对话历史」和「新增运行时状态」

源码 `session.py` 已经有一套 session 概念，但它保存的是**对话历史**：

```python
# 现有 session.py 保存的内容
{"id": session_id, "model": model, "saved_at": ..., "messages": messages}
```

这套是 `save_session`/`load_session`，给 `/save` `/sessions` `/resume` 用的，**不需要改，也不是这次要扩展的东西**。

Web 版新增的是另一层——**运行时状态（runtime state）**，跟对话历史是两个概念，不要混在一起：

```python
# 新增：Web Agent Session 运行时状态（内存态）
{
  "status": "RUNNING" | "WAIT_CONFIRM" | "DONE",
  "pending_confirm": {
      "id": str,
      "type": "edit_file" | "bash",
      "diff": str | None,
      "command": str | None,
  } | None,
  # threading.Event 对象本身不放这个 dict 里（不可序列化），
  # 由 3.2 节的 ConfirmRegistry 统一管理 event_id -> Event 的映射，
  # 这里的 pending_confirm 只存展示所需的纯数据快照
}
```

MVP 只做**内存态**，不接 Redis/DB。验证目标不是"重启服务后能恢复"，而是"**浏览器刷新页面后，如果有一个确认还没处理，UI 能重新显示出确认框**"——`GET /api/session/{id}/pending` 查一下当前 `pending_confirm` 是否非空就够了。

------

## 4. Web 后端设计

```
corecoder/web/
├── server.py           run_web(): 起 uvicorn + webbrowser.open + token
├── app.py               路由注册
├── routes/
│   ├── chat.py          POST /api/chat        (SSE)
│   ├── confirm.py        POST /api/confirm
│   ├── session.py         GET  /api/session/{id}/pending
│   └── workspace.py       GET  /api/tree, GET /api/file
├── workspace_fs.py        统一路径解析 + 越界校验（read/write/edit 工具与 /api/tree /api/file 共用）
├── events.py               模块级事件总线：set_emitter() 由 server.py 注入 SSE 推送函数，
│                            emit() 是唯一出口——tool_start（通过 on_tool 回调间接到达：
│                            agent.chat() 仍以参数形式接收 on_tool，server.py 里这个回调的
│                            实现内部调 events.emit）、tool_end（agent.chat() 直接调用）、
│                            confirm_required（EditFileTool/BashTool 内部调用）最终都走这一个函数
└── confirm_registry.py     ConfirmRegistry：event_id ↔ threading.Event 的加锁封装，
                             管 create/wait/resolve，超时与 /api/confirm 到达后都会自动清理
```

`workspace_fs.py` 是文件工具（`read_file`/`write_file`/`edit_file`）和文件树 API 共用的同一份路径安全逻辑——避免在多处各写一遍越界校验，出现遗漏。`events.py` 和 `confirm_registry.py` 是 3.2 节里"第零步"要先跑通的两个基础模块，`EditFileTool`/`BashTool` 的确认逻辑、`agent.chat()` 的 `tool_end` 都建在它们之上，开发顺序上要排在两个工具的改造之前。

------

## 5. API 设计

```
POST /api/chat            body: {message}
SSE 事件：
  token             {"text"}
  tool_start        {"id","name","args"}
  tool_end          {"id","result"}
  confirm_required   {"id","action","file_path"?,"diff"?,"command"?,"reason"?}
  done               {"tokens"?}

POST /api/confirm         body: {id, approve: bool}
                          若 id 已超时或不存在（ConfirmRegistry.resolve 返回 False），
                          返回明确的 4xx 错误，而不是静默忽略
GET  /api/session/{id}/pending    刷新页面后恢复挂起的确认状态

GET  /api/tree             文件树
GET  /api/file?path=xxx    文件内容
```

（安全性说明：server 只绑 `127.0.0.1`，URL 带随机 token 防本地跨站请求，具体见下方"安全设计"一节。）

------

## 6. 前端设计

技术栈：Vue3 + TypeScript + Tailwind CSS + Naive UI + Monaco Editor

```
┌──────────────┬─────────────────────────┐
│  文件树        │  Chat + Agent Timeline    │
│  FileTree.vue │  ChatPanel.vue            │
│               │  ToolCallCard.vue          │
│               │   （edit_file 命中时露出     │
│               │    "查看修改"按钮，点击展开     │
│               │    DiffViewer.vue）          │
│               │  ConfirmModal.vue           │
└──────────────┴─────────────────────────┘
```

**不做独立 Diff 页面**：`DiffViewer.vue` 作为独立组件，由 `ToolCallCard` 触发展开（比如侧滑面板/Modal 内嵌），而不是把 Monaco diff 逻辑直接写死在 `ToolCallCard` 内部——两者职责分开：`ToolCallCard` 只管展示工具调用的状态和摘要，`DiffViewer` 专门封装 Monaco Diff Editor 的加载和渲染，之后如果要在别的场景复用 diff 展示（比如 `/diff` 历史修改列表），不用动 `ToolCallCard`。保持"看着 agent 实时干活"这一条主体验线，不跳转到独立页面。

```
src/
  components/
    FileTree.vue
    ChatPanel.vue
    ToolCallCard.vue      触发展示，不内含 diff 渲染逻辑
    DiffViewer.vue         封装 Monaco Diff Editor，接收 old/new content 或 diff 文本
    ConfirmModal.vue       edit / bash 命令两种确认场景复用同一个组件，确认时可直接嵌入 DiffViewer 预览
  composables/
    useAgentStream.ts       fetch + ReadableStream 手写 SSE 解析（POST body 场景 EventSource 不支持）
  store/
    chat.ts (pinia)
    workspace.ts (pinia)
```

Monaco 用动态 `import()` 懒加载，只在展开 diff 时才加载，不进主 bundle。

------

## 7. 安全设计

1. Web server 只绑定 `127.0.0.1`，不监听 `0.0.0.0`
2. URL 携带随机 token（类似 Jupyter 的做法），防止本地其他浏览器标签页的恶意网页发起跨站请求打到本地 agent（本地 HTTP 服务是真实存在过的攻击面，Jupyter 曾因此有过 CVE）
3. `workspace_fs.py` 统一做路径越界校验（`is_relative_to(workspace_root)`），防止 `../../` 之类跳出 workspace
4. bash 黑名单命中后走确认流程而不是静默放行，普通命令不打断，兼顾安全与体验

------

## 8. MVP 里程碑

| 阶段 | 交付                                                         | 验证点                                                       |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| M1   | `corecoder web` 启动，浏览器自动打开，Chat 页面能对话，SSE token 流式显示 | 启动流程、workspace 绑定、DeepSeek 联通                      |
| M2   | 文件树 + `ToolCallCard` 展示工具调用过程（读文件/搜索/执行命令实时可见）；**先跑通 `events.py` 事件总线 + `agent.chat()` 里单工具/并行两条路径都调用 `events.emit("tool_end", ...)` + `ConfirmRegistry` 最小验证**（哪怕先打印到 console，不接 SSE 也要验证调用链通） | `workspace_fs.py` 路径安全、SSE tool_start/tool_end 都能正常触发（单工具与并行路径都要验证）、事件总线单例可用 |
| M3   | 改造 `EditFileTool`：diff 提前到 write 之前算出，加确认阻塞流程（基于 M2 跑通的 `events.emit` + `ConfirmRegistry`）；`ConfirmModal` 弹窗确认，`DiffViewer.vue` 独立组件展示 Monaco diff（由 `ToolCallCard` 触发，不写死在其内部） | 确认机制在具体工具里先跑通、组件职责分离（此里程碑把"确认"和"diff展示"合并，避免逻辑割裂） |
| M4   | 改造 `BashTool`：命中黑名单时从直接拒绝改为走确认流程；对比 M3/M4 两份确认逻辑的重复部分，提炼 `ConfirmableTool` 抽象；`GET /api/session/{id}/pending` 支持刷新页面恢复挂起状态；明确子 Agent 确认事件走同一 SSE 通道 | 人机协作闭环、基于两个真实实现的抽象、基本的状态恢复         |

------

## 9. 最终效果示例

用户：

```
帮我在 login 接口加上频率限制
```

系统：

```
读取相关文件（read_file / grep 实时可见）
    ↓
生成修改方案（edit_file，diff 提前算出）
    ↓
前端弹出确认框 + diff 预览
    ↓
用户确认
    ↓
写入文件，Timeline 展示最终 diff
    ↓
如需验证，执行 npm test（若命中黑名单则再次确认）
    ↓
完成
```

------

## 10. 简历表述参考

> 基于开源 minimal coding agent（CoreCoder）二次开发，改造其原有 `edit_file`/`bash` 工具，引入 Human-in-the-loop 审批机制：设计模块级事件总线打通 Tool 执行层与 SSE 推送的调用链，通过加锁的 `ConfirmRegistry` 管理 `threading.Event` 实现工具调用中途挂起等待前端确认、超时清理、并发安全，并从两个具体实现中提炼出可复用的 `ConfirmableTool` 抽象；区分原有的对话历史持久化（`session.py`）与新增的 Agent 运行时状态管理；将原有 CLI 单进程工作目录假设改造为显式 workspace 绑定并补充路径越界校验；前端基于 Vue3 + Monaco Editor 实现 agent 执行过程与代码 diff 的实时可视化。