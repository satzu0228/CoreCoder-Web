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

from fastapi import APIRouter, Request
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


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    agent = request.app.state.agent
    events: queue.Queue = queue.Queue()

    def push(event_type: str, data: dict):
        events.put({**data, "type": event_type})

    def on_token(text: str):
        events.put({"type": "token", "text": text})

    def on_tool(tool_id: str, name: str, args: dict):
        events.put({"type": "tool_start", "id": tool_id, "name": name, "args": args})

    def worker():
        set_emitter(push)
        try:
            agent.chat(req.message, on_token=on_token, on_tool=on_tool)
        except Exception as e:
            events.put({"type": "error", "message": str(e)})
        finally:
            clear_emitter()
            events.put(_DONE)

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        while True:
            item = await run_in_threadpool(events.get)
            if item is _DONE:
                yield _sse({"type": "done"})
                break
            yield _sse(item)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
