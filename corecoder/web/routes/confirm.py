"""POST /api/confirm - handle user confirmation/rejection of pending actions."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..confirm_registry import registry

router = APIRouter()


class ConfirmRequest(BaseModel):
    id: str
    approve: bool


@router.post("/api/confirm")
async def confirm(req: ConfirmRequest):
    """Record user's choice for a pending confirmation.

    Args:
        id: the confirmation event_id from the SSE confirm_required event
        approve: True to approve, False to reject

    Returns:
        {status: "ok"} on success

    Raises:
        404: if the event_id doesn't exist or has already timed out.
             This prevents silent failures if the frontend's retry/retry
             logic sends a confirmation after the tool has already timed out.
    """
    if not registry.resolve(req.id, req.approve):
        raise HTTPException(
            status_code=404,
            detail=f"Confirmation {req.id} not found or already timed out",
        )
    return {"status": "ok"}


@router.post("/api/sessions/{session_id}/confirm")
async def confirm_session(session_id: str, req: ConfirmRequest, request: Request):
    manager = request.app.state.sessions
    try:
        manager.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    if manager.running_session_id != session_id:
        raise HTTPException(status_code=409, detail="This conversation is not waiting for confirmation")
    pending = registry.get_pending()
    if not pending or pending.get("id") != req.id or not registry.resolve(req.id, req.approve):
        raise HTTPException(status_code=404, detail="Confirmation not found or already completed")
    manager.set_status(session_id, "running")
    return {"status": "ok"}
