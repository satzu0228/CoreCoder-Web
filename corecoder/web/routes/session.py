"""In-memory Web session state used to restore the UI after a refresh."""

import json

from fastapi import APIRouter, Request

from ..confirm_registry import registry

router = APIRouter()


@router.get("/api/session/pending")
async def get_pending_confirm() -> dict:
    """Get current pending confirmation (if any) for page refresh recovery.

    Returns:
        {
          "pending": {
            "id": "...",
            "action": "edit_file" | "bash",
            "file_path": "...",  # if edit_file
            "diff": "...",       # if edit_file
            "command": "...",    # if bash
            "reason": "...",     # if bash
          }
        }
        or {"pending": None} if no pending confirmation.

    When user refreshes the browser, the frontend calls this endpoint to check
    if there's a pending confirmation that needs to be displayed. If so, the
    ConfirmModal is shown with the full payload restored.

    Note: Token validation is done by middleware; this endpoint assumes valid token.
    """
    pending_data = registry.get_pending()
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


@router.get("/api/session/messages")
async def get_session_messages(request: Request) -> dict:
    """Return a stable UI DTO, not the Agent's provider-specific message list."""
    messages = list(request.app.state.agent.messages)
    return {
        "messages": serialize_messages(messages),
        "running": bool(request.app.state.agent_running),
    }
