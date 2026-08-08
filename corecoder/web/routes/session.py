"""Session and state endpoints for agent runtime.

Handles queries for pending confirmations (used to restore UI after page refresh).
"""

from fastapi import APIRouter, Query
from ..confirm_registry import registry

router = APIRouter()


@router.get("/api/session/pending")
async def get_pending_confirm(token: str = Query(...)) -> dict:
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
