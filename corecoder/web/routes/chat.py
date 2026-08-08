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
from collections import deque

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..events import set_emitter, clear_emitter

router = APIRouter()

# sentinel distinguishing "stream finished" from any real (possibly falsy) event
_DONE = object()
_MAX_BUFFER_SIZE = 500


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

    # Store queue and buffer on app state for reconnect support
    if not hasattr(request.app.state, "event_queues"):
        request.app.state.event_queues: dict = {}
    if not hasattr(request.app.state, "event_buffers"):
        request.app.state.event_buffers: dict = {}
    request.app.state.event_queues[session_id] = events
    buf: deque[dict] = deque(maxlen=_MAX_BUFFER_SIZE)
    request.app.state.event_buffers[session_id] = buf
    seq_counter = [0]  # mutable counter for closure

    def tagged(data: dict) -> dict:
        seq_counter[0] += 1
        result = {**data, "sequence": seq_counter[0]}
        return {**result, "session_id": session_id} if tag_session else result

    def push(event_type: str, data: dict):
        if event_type == "confirm_required":
            manager.set_status(session_id, "waiting_confirmation")
        item = tagged({**data, "type": event_type})
        buf.append(item)
        events.put(item)

    def on_token(text: str):
        item = tagged({"type": "token", "text": text})
        buf.append(item)
        events.put(item)

    def on_tool(tool_id: str, name: str, args: dict):
        item = tagged({"type": "tool_start", "id": tool_id, "name": name, "args": args})
        buf.append(item)
        events.put(item)

    def worker():
        set_emitter(push)
        request.app.state.agent_running = True
        final_status = "idle"
        cancel_ev = manager.cancel_event(session_id)
        try:
            agent.chat(req.message, on_token=on_token, on_tool=on_tool, cancel_event=cancel_ev)
        except Exception as e:
            final_status = "error"
            events.put(tagged({"type": "error", "message": str(e)}))
        finally:
            request.app.state.agent_running = False
            clear_emitter()
            # Determine final status considering cancel
            if cancel_ev and cancel_ev.is_set():
                final_status = "cancelled" if final_status != "error" else "error"
            manager.finish_run(session_id, final_status)
            # Push final done event with the final session status
            events.put(tagged({"type": "done", "status": final_status}))
            events.put(_DONE)

    events.put(tagged({"type": "status", "phase": "connecting", "message": "正在连接模型"}))
    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        started_at = time.monotonic()
        try:
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
                    break
                yield _sse(item)
        finally:
            # Clean up on disconnect
            request.app.state.event_queues.pop(session_id, None)
            request.app.state.event_buffers.pop(session_id, None)

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


@router.post("/api/sessions/{session_id}/cancel")
async def cancel_run(session_id: str, request: Request):
    """Cancel a running task for the given session.

    Sets the cancel event checked by the agent loop, wakes pending confirmations,
    and attempts to kill any in-flight bash subprocess.
    """
    manager = request.app.state.sessions
    try:
        session = manager.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None

    if not manager.cancel_run(session_id):
        raise HTTPException(status_code=409, detail="No running task to cancel for this session")

    # Publish the transition before closing resources: closing the model stream
    # can let the worker finish immediately, and a later write would otherwise
    # race cancelled -> cancelling in the wrong direction.
    manager.set_status(session_id, "cancelling")

    # Wake a model SDK blocked while reading the next streaming chunk.
    cancel_model = getattr(session.agent.llm, "cancel_current_request", None)
    if callable(cancel_model):
        cancel_model()

    # Wake any pending confirmation so the tool returns immediately
    from ..confirm_registry import registry
    registry.cancel_all()

    # Kill any in-flight bash subprocess
    from ...tools.bash import cancel_current_command
    cancel_current_command()

    return {"status": "cancelling"}


@router.get("/api/sessions/{session_id}/events")
async def session_events(
    session_id: str,
    request: Request,
    after: int = Query(0, description="Last received sequence number"),
):
    """Reconnect to an active run's event stream after disconnection.

    If the session is running, replays buffered events with sequence > `after`,
    then subscribes to the live event stream. If the buffer doesn't go back far
    enough, sends a resync_required event with the full session state.

    Returns 404 if the session doesn't exist, 409 if no run is active.
    """
    manager = request.app.state.sessions
    try:
        manager.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None

    event_queues = getattr(request.app.state, "event_queues", {}) or {}
    event_buffers = getattr(request.app.state, "event_buffers", {}) or {}
    live_queue: queue.Queue | None = event_queues.get(session_id)
    buf: deque | None = event_buffers.get(session_id)

    if live_queue is None or buf is None:
        # No active run for this session — send full state for resync
        session = manager.get(session_id)
        messages = list(session.agent.messages)
        from .session import serialize_messages
        resync = {
            "type": "resync_required",
            "session_id": session_id,
            "status": session.status,
            "messages": serialize_messages(messages),
        }

        async def resync_stream():
            yield _sse(resync)

        return StreamingResponse(
            resync_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    async def replay_and_stream():
        # Phase 1: replay buffered events the client missed
        replayed = 0
        for item in buf:
            seq = item.get("sequence", 0)
            if seq > after:
                yield _sse(item)
                replayed += 1

        if replayed == 0 and after > 0:
            # Buffer doesn't cover the requested sequence — client needs full resync
            session = manager.get(session_id)
            messages = list(session.agent.messages)
            from .session import serialize_messages
            yield _sse({
                "type": "resync_required",
                "session_id": session_id,
                "status": session.status,
                "messages": serialize_messages(messages),
            })

        # Phase 2: subscribe to live events
        while True:
            try:
                item = await run_in_threadpool(live_queue.get, True, 1.0)
            except queue.Empty:
                # Heartbeat while waiting for the next live event
                continue
            if item is _DONE:
                break
            yield _sse(item)

    return StreamingResponse(
        replay_and_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """Compatibility route forwarding to the most recent conversation."""
    session = request.app.state.sessions.ensure_default()
    return _start_chat(req, request, session.id, tag_session=False)
