"""Module-level event bus.

server.py injects the real SSE push function once at startup via set_emitter().
After that, any module (agent.py, tools/edit.py, tools/bash.py) can call
emit() without knowing anything about the SSE transport.

Thread safety: set_emitter() is called once before any requests arrive.
emit() may be called from worker threads concurrently; the injected function
(queue.Queue.put) is itself thread-safe, so no extra locking is needed here.
"""

_sse_emit = None


def set_emitter(fn) -> None:
    """Inject the SSE push function. Called once by server.py at startup."""
    global _sse_emit
    _sse_emit = fn


def clear_emitter() -> None:
    """Remove the current emitter (used between requests or in tests)."""
    global _sse_emit
    _sse_emit = None


def has_emitter() -> bool:
    """Return whether a Web SSE request is currently receiving tool events."""
    return _sse_emit is not None


def emit(event_type: str, data: dict) -> None:
    """Push an event. No-op if no emitter is registered."""
    if _sse_emit:
        _sse_emit(event_type, data)
