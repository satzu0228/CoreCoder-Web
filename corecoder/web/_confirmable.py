"""Shared confirmation flow for Web tools that need user approval."""

import threading

from . import events
from .confirm_registry import ConfirmResult, registry


# The MVP UI displays one confirmation modal. Serializing requests here keeps
# parallel confirmable tool calls from overwriting each other in the frontend.
_confirmation_gate = threading.Lock()


def request_confirmation(action: str, payload: dict, timeout: float = 300) -> ConfirmResult:
    """Register, emit, and wait for one serialized confirmation request."""
    full_payload = {**payload, "action": action}
    with _confirmation_gate:
        event_id = registry.create(payload=full_payload)
        events.emit("confirm_required", {"id": event_id, **full_payload})
        return registry.wait(event_id, timeout=timeout)
