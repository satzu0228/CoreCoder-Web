"""Confirmation request registry for human-in-the-loop tool execution.

When a tool (edit_file, bash) needs user approval before proceeding, it:
1. Creates a confirmation request: registry.create() -> event_id
2. Emits the request to the frontend via SSE
3. Blocks waiting: registry.wait(event_id, timeout=300)
4. Frontend responds via POST /api/confirm with the user's choice
5. resolve(event_id, approve) unblocks the tool

Thread-safe: concurrent edit_file calls each get their own event_id, and
wait/resolve operations are protected by a lock.

Key invariant: wait() always cleans up both _events and _results regardless
of timeout or normal return, so no stale entries accumulate.
"""

import threading
import uuid


class ConfirmRegistry:
    """Thread-safe registry of pending confirmations."""

    def __init__(self):
        self._events: dict[str, threading.Event] = {}
        self._results: dict[str, bool] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        """Create a new confirmation request.

        Returns: event_id to pass to wait() and to emit in the SSE event.
        """
        event_id = uuid.uuid4().hex
        with self._lock:
            self._events[event_id] = threading.Event()
        return event_id

    def wait(self, event_id: str, timeout: float = 300) -> bool:
        """Block until the user confirms/rejects or timeout expires.

        Args:
            event_id: the ID returned by create()
            timeout: max seconds to wait (default 5 min)

        Returns:
            True if user approved, False if user rejected or timed out.

        Always cleans up _events and _results entries before returning,
        even on timeout, to prevent stale state accumulation.
        """
        with self._lock:
            if event_id not in self._events:
                # Already cleaned up (shouldn't happen in normal flow, but defensive)
                return False
            ev = self._events[event_id]

        # Wait outside the lock so resolve() can acquire it to set() the event
        ev.wait(timeout=timeout)

        with self._lock:
            approved = self._results.pop(event_id, False)
            self._events.pop(event_id, None)
        return approved

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
            self._results[event_id] = approve
            self._events[event_id].set()
        return True


# Module-level singleton; safe for single-user assumption in MVP.
# If v2 adds multi-workspace support, this becomes per-workspace state.
registry = ConfirmRegistry()
