"""Workspace-scoped Web conversation APIs."""

import json

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..confirm_registry import registry


router = APIRouter()


class UpdateSessionRequest(BaseModel):
    title: str


def _manager(request: Request):
    return request.app.state.sessions


def _get_session(request: Request, session_id: str):
    try:
        return _manager(request).get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None


@router.get("/api/sessions")
async def list_sessions(
    request: Request,
    search: str = Query(default=None, description="Filter sessions by title or preview text"),
    archived: bool = Query(default=False, description="Include archived sessions"),
) -> dict:
    manager = _manager(request)
    return {
        "workspace": {"id": manager.workspace_id, "name": manager.workspace_name},
        "sessions": manager.list(search=search, include_archived=archived),
        "running_session_id": manager.running_session_id,
    }


@router.post("/api/sessions", status_code=201)
async def create_session(request: Request) -> dict:
    return {"session": _manager(request).create().summary()}


@router.get("/api/sessions/{session_id}")
async def get_session(request: Request, session_id: str) -> dict:
    session = _get_session(request, session_id)
    return {
        "session": session.summary(),
        "messages": serialize_messages(list(session.agent.messages)),
        "token_stats": session.agent.token_stats(),
    }


@router.patch("/api/sessions/{session_id}")
async def update_session(request: Request, session_id: str, body: UpdateSessionRequest) -> dict:
    try:
        session = _manager(request).rename(session_id, body.title)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"session": session.summary()}


@router.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(request: Request, session_id: str):
    try:
        _manager(request).delete(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except RuntimeError:
        raise HTTPException(status_code=409, detail="A running conversation cannot be deleted") from None


class BatchDeleteRequest(BaseModel):
    session_ids: list[str]


@router.post("/api/sessions/{session_id}/archive")
async def archive_session(request: Request, session_id: str) -> dict:
    """Archive a session (soft-delete)."""
    try:
        session = _manager(request).archive(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except RuntimeError:
        raise HTTPException(status_code=409, detail="A running conversation cannot be archived") from None
    return {"session": session.summary()}


@router.post("/api/sessions/{session_id}/unarchive")
async def unarchive_session(request: Request, session_id: str) -> dict:
    """Restore an archived session."""
    try:
        session = _manager(request).unarchive(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    return {"session": session.summary()}


@router.delete("/api/sessions", status_code=200)
async def batch_delete_sessions(request: Request, body: BatchDeleteRequest) -> dict:
    """Delete multiple sessions at once. Skips running sessions."""
    deleted = _manager(request).batch_delete(body.session_ids)
    return {"deleted": deleted}


@router.get("/api/sessions/{session_id}/pending")
async def get_session_pending(request: Request, session_id: str) -> dict:
    _get_session(request, session_id)
    manager = _manager(request)
    pending_data = registry.get_pending() if manager.running_session_id == session_id else None
    return {"pending": pending_data}

def _parse_arguments(raw_arguments) -> dict:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str):
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {"raw": raw_arguments}


def serialize_messages(messages: list[dict]) -> list[dict]:
    """Convert OpenAI history into the compact DTO consumed by the Web UI."""
    result: list[dict] = []
    active_assistant: dict | None = None
    tool_calls: dict[str, dict] = {}

    for index, message in enumerate(messages):
        role = message.get("role")
        if role == "user":
            result.append({
                "id": f"history-{index}",
                "role": "user",
                "content": message.get("content") or "",
            })
            active_assistant = None
            continue

        if role == "assistant":
            if active_assistant is None:
                active_assistant = {
                    "id": f"history-{index}",
                    "role": "assistant",
                    "content": "",
                    "toolCalls": [],
                }
                result.append(active_assistant)

            content = message.get("content") or ""
            if content:
                active_assistant["content"] += content

            for raw_call in message.get("tool_calls") or []:
                function = raw_call.get("function") or {}
                tool_call = {
                    "id": raw_call.get("id") or f"history-tool-{index}",
                    "name": function.get("name") or "unknown",
                    "args": _parse_arguments(function.get("arguments")),
                    "status": "running",
                }
                active_assistant["toolCalls"].append(tool_call)
                tool_calls[tool_call["id"]] = tool_call
            continue

        if role == "tool":
            tool_call = tool_calls.get(message.get("tool_call_id"))
            if tool_call is not None:
                tool_call["status"] = "done"
                tool_call["result"] = message.get("content") or ""

    return result


