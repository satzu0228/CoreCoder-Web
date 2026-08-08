"""POST /api/chat - runs one agent turn, streams tokens back over SSE.

agent.chat() is synchronous and drives its on_token callback from whatever
thread calls it. To turn that into an async SSE stream without touching
agent.py, we run chat() in a worker thread and relay events through a
thread-safe queue: the worker puts items on the queue, the async generator
drains it and yields SSE frames.

The events module is wired up at the start of each worker so that tool_start,
tool_end, and (later) confirm_required all flow through the same queue.
"""

import json
import queue
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..events import set_emitter, clear_emitter

router = APIRouter()

# sentinel distinguishing "stream finished" from any real (possibly falsy) event
_DONE = object()


class ChatRequest(BaseModel):
    message: str


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _start_chat(req: ChatRequest, request: Request, session_id: str, *, tag_session: bool = True):
    manager = request.app.state.sessions
    try:
        session = manager.begin_run(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "Another conversation is already running", "session_id": str(exc)},
        ) from exc

    agent = session.agent
    events: queue.Queue = queue.Queue()

    def tagged(data: dict) -> dict:
        return {**data, "session_id": session_id} if tag_session else data

    def push(event_type: str, data: dict):
        if event_type == "confirm_required":
            manager.set_status(session_id, "waiting_confirmation")
        events.put(tagged({**data, "type": event_type}))

    def on_token(text: str):
        events.put(tagged({"type": "token", "text": text}))

    def on_tool(tool_id: str, name: str, args: dict):
        events.put(tagged({"type": "tool_start", "id": tool_id, "name": name, "args": args}))

    def worker():
        set_emitter(push)
        request.app.state.agent_running = True
        final_status = "idle"
        try:
            agent.chat(req.message, on_token=on_token, on_tool=on_tool)
        except Exception as e:
            final_status = "error"
            events.put(tagged({"type": "error", "message": str(e)}))
        finally:
            request.app.state.agent_running = False
            clear_emitter()
            manager.finish_run(session_id, final_status)
            events.put(_DONE)

    events.put(tagged({"type": "status", "phase": "connecting", "message": "正在连接模型"}))
    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        started_at = time.monotonic()
        while True:
            try:
                item = await run_in_threadpool(events.get, True, 1.0)
            except queue.Empty:
                elapsed = max(1, int(time.monotonic() - started_at))
                if elapsed < 8:
                    message = f"等待模型响应 · {elapsed}s"
                    phase = "waiting"
                elif elapsed < 20:
                    message = f"模型正在处理上下文 · {elapsed}s"
                    phase = "processing"
                else:
                    message = f"任务较复杂，模型仍在处理 · {elapsed}s"
                    phase = "processing"
                yield _sse(tagged({"type": "status", "phase": phase, "message": message, "elapsed": elapsed}))
                continue
            if item is _DONE:
                yield _sse(tagged({"type": "done"}))
                break
            yield _sse(item)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/sessions/{session_id}/chat")
async def session_chat(session_id: str, req: ChatRequest, request: Request):
    return _start_chat(req, request, session_id)


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """Compatibility route forwarding to the most recent conversation."""
    session = request.app.state.sessions.ensure_default()
    return _start_chat(req, request, session.id, tag_session=False)
