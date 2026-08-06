"""Confirmation flow helpers for tools that request user approval.

Used by bash.py and edit.py to emit confirmation requests and wait for user response.
Provides a thin wrapper around ConfirmRegistry for readable, repeatable patterns.
"""

from .confirm_registry import registry, ConfirmResult
from . import events


def request_bash_confirmation(command: str, reason: str) -> ConfirmResult:
    """
    Request user confirmation for a dangerous bash command.

    Args:
        command: The shell command that triggered the dangerous pattern
        reason: Human-readable reason (e.g., "force recursive delete")

    Returns:
        ConfirmResult.APPROVED if user approved execution
        ConfirmResult.REJECTED if user rejected
        ConfirmResult.TIMEOUT if no response within 300s

    The confirmation payload is stored in registry for page refresh recovery.
    """
    payload = {
        "action": "bash",
        "command": command,
        "reason": reason,
    }
    event_id = registry.create(payload=payload)
    # Emit to frontend with id included
    events.emit("confirm_required", {"id": event_id, **payload})
    return registry.wait(event_id, timeout=300)
