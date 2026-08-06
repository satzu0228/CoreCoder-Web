"""Confirmation request registry for human-in-the-loop tool execution.

When a tool (edit_file, bash) needs user approval before proceeding, it:
1. Creates a confirmation request: registry.create() -> event_id
2. Emits the request to the frontend via SSE with full payload
3. Blocks waiting: registry.wait(event_id, timeout=300)
4. Frontend responds via POST /api/confirm with the user's choice
5. resolve(event_id, approve) unblocks the tool

Thread-safe: concurrent edit_file calls each get their own event_id, and
wait/resolve operations are protected by a lock.

Key invariant: wait() always cleans up both _events and _results regardless
of timeout or normal return, so no stale entries accumulate.

Registry also stores the full confirmation payload (action, file_path/command, etc.)
for page refresh recovery via get_pending().
"""

import threading
import uuid
from enum import Enum


class ConfirmResult(Enum):
    """Three-state result of a confirmation request."""
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ConfirmRegistry:
    """Thread-safe registry of pending confirmations."""

    def __init__(self):
        self._events: dict[str, threading.Event] = {}
        self._results: dict[str, ConfirmResult] = {}
        self._payloads: dict[str, dict] = {}  # Store full confirm payload for recovery
        self._lock = threading.Lock()

    def create(self, payload: dict | None = None) -> str:
        """Create a new confirmation request.

        Args:
            payload: The confirmation event payload (action, file_path/command, etc.)
                     Will be stored and returned by get_pending() for page recovery.

        Returns: event_id to pass to wait() and to emit in the SSE event.
        """
        event_id = uuid.uuid4().hex
        with self._lock:
            self._events[event_id] = threading.Event()
            if payload:
                self._payloads[event_id] = {"id": event_id, **payload}
        return event_id

    def wait(self, event_id: str, timeout: float = 300) -> ConfirmResult:
        """Block until the user confirms/rejects or timeout expires.

        Args:
            event_id: the ID returned by create()
            timeout: max seconds to wait (default 5 min)

        Returns:
            ConfirmResult.APPROVED if user approved
            ConfirmResult.REJECTED if user rejected
            ConfirmResult.TIMEOUT if no response within timeout

        Always cleans up _events, _results, and _payloads entries before returning,
        even on timeout, to prevent stale state accumulation.
        """
        with self._lock:
            if event_id not in self._events:
                # Already cleaned up (shouldn't happen in normal flow, but defensive)
                return ConfirmResult.TIMEOUT
            ev = self._events[event_id]

        # Wait outside the lock so resolve() can acquire it to set() the event
        ev.wait(timeout=timeout)

        with self._lock:
            result = self._results.pop(event_id, ConfirmResult.TIMEOUT)
            self._events.pop(event_id, None)
            self._payloads.pop(event_id, None)
        return result

    def resolve(self, event_id: str, approve: bool) -> bool:
        """Record user's choice and unblock the waiting tool.

        Args:
            event_id: the ID from the /api/confirm request body
            approve: True if user approved, False if rejected

        Returns:
            True if the event was found and unblocked, False if already
            timed out or never existed (allowing the route to return 4xx).
        """
        with self._lock:
            if event_id not in self._events:
                # Timed out already, or invalid ID
                return False
            self._results[event_id] = ConfirmResult.APPROVED if approve else ConfirmResult.REJECTED
            self._events[event_id].set()
        return True

    def get_pending(self) -> dict | None:
        """Get current pending confirmation (if any) for page refresh recovery.

        Returns:
            Dict with full payload (id, action, file_path/command, diff/reason, etc.)
            or None if no pending confirmation.

        Used by GET /api/session/pending to restore UI after page reload.
        """
        with self._lock:
            # Return the first (and should be only one) pending confirmation
            for event_id, payload in self._payloads.items():
                if event_id in self._events and not self._events[event_id].is_set():
                    return payload
        return None


# Module-level singleton; safe for single-user assumption in MVP.
# If v2 adds multi-workspace support, this becomes per-workspace state.
registry = ConfirmRegistry()
