"""Tests for the FastAPI Web layer: token auth and the SSE chat stream.

Uses ScriptedLLM so no real API key or network call is needed.
"""

import json

from fastapi.testclient import TestClient

from corecoder.agent import Agent
from corecoder.llm import LLMResponse, ScriptedLLM
from corecoder.web.app import create_app

TOKEN = "test-token"


def _make_client(turns):
    agent = Agent(llm=ScriptedLLM(turns), tools=[])
    app = create_app(agent, TOKEN)
    return TestClient(app)


def _parse_sse(text: str) -> list[dict]:
    events = []
    for frame in text.split("\n\n"):
        if frame.startswith("data: "):
            events.append(json.loads(frame[len("data: "):]))
    return events


def test_index_is_public_and_needs_no_token():
    client = _make_client([LLMResponse(content="hi")])
    resp = client.get("/")
    assert resp.status_code == 200
    assert "CoreCoder" in resp.text


def test_chat_without_token_is_rejected():
    client = _make_client([LLMResponse(content="hi")])
    resp = client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 403


def test_chat_with_wrong_token_is_rejected():
    client = _make_client([LLMResponse(content="hi")])
    resp = client.post(
        "/api/chat",
        json={"message": "hello"},
        headers={"X-CoreCoder-Token": "wrong"},
    )
    assert resp.status_code == 403


def test_chat_streams_tokens_then_done():
    client = _make_client([LLMResponse(content="hello world")])
    resp = client.post(
        "/api/chat",
        json={"message": "say hi"},
        headers={"X-CoreCoder-Token": TOKEN},
    )
    assert resp.status_code == 200

    events = _parse_sse(resp.text)
    assert events[-1] == {"type": "done"}
    token_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert token_text == "hello world"


def test_chat_reports_agent_errors_without_crashing_the_stream():
    class _BrokenLLM:
        model = "broken"
        total_prompt_tokens = 0
        total_completion_tokens = 0

        def chat(self, messages, tools=None, on_token=None):
            raise RuntimeError("boom")

    agent = Agent(llm=_BrokenLLM(), tools=[])
    app = create_app(agent, TOKEN)
    client = TestClient(app)

    resp = client.post(
        "/api/chat",
        json={"message": "say hi"},
        headers={"X-CoreCoder-Token": TOKEN},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "error" and "boom" in e["message"] for e in events)


def test_chat_accepts_token_as_query_param_too():
    client = _make_client([LLMResponse(content="ok")])
    resp = client.post(
        "/api/chat",
        params={"token": TOKEN},
        json={"message": "hello"},
    )
    assert resp.status_code == 200


def test_chat_emits_tool_start_and_tool_end_events():
    """Verify tool_start and tool_end events are emitted in the SSE stream."""
    from corecoder.llm import ToolCall

    # Create a response with a single tool call
    tool_calls = [
        ToolCall(
            id="call_1",
            name="bash",
            arguments={"command": "echo hello"},
        )
    ]
    # After tool execution, LLM returns final text
    turns = [
        LLMResponse(content="", tool_calls=tool_calls),
        LLMResponse(content="done"),
    ]

    from corecoder.tools import get_tool
    bash_tool = get_tool("bash")
    agent = Agent(llm=ScriptedLLM(turns), tools=[bash_tool])
    app = create_app(agent, TOKEN)
    client = TestClient(app)

    resp = client.post(
        "/api/chat",
        json={"message": "run echo"},
        headers={"X-CoreCoder-Token": TOKEN},
    )
    assert resp.status_code == 200

    events = _parse_sse(resp.text)
    assert events[-1] == {"type": "done"}

    # Verify tool_start event
    tool_start_events = [e for e in events if e["type"] == "tool_start"]
    assert len(tool_start_events) == 1
    assert tool_start_events[0]["id"] == "call_1"
    assert tool_start_events[0]["name"] == "bash"
    assert tool_start_events[0]["args"]["command"] == "echo hello"

    # Verify tool_end event
    tool_end_events = [e for e in events if e["type"] == "tool_end"]
    assert len(tool_end_events) == 1
    assert tool_end_events[0]["id"] == "call_1"
    assert tool_end_events[0]["name"] == "bash"
    assert "hello" in tool_end_events[0]["result"]


def test_confirm_endpoint_rejects_invalid_token():
    """POST /api/confirm rejects requests without valid token."""
    client = _make_client([LLMResponse(content="hi")])
    resp = client.post(
        "/api/confirm",
        json={"id": "some-id", "approve": True},
    )
    assert resp.status_code == 403


def test_confirm_endpoint_resolves_pending_confirmation():
    """POST /api/confirm correctly resolves a pending confirmation."""
    from corecoder.web.confirm_registry import registry

    client = _make_client([LLMResponse(content="ok")])

    # Create a pending confirmation
    event_id = registry.create(payload={"action": "test", "test": "data"})

    # Approve it via the endpoint
    resp = client.post(
        "/api/confirm",
        json={"id": event_id, "approve": True},
        headers={"X-CoreCoder-Token": TOKEN},
    )
    assert resp.status_code == 200


def test_confirm_returns_404_for_expired_id():
    """POST /api/confirm returns 404 for timed-out or non-existent IDs."""
    client = _make_client([LLMResponse(content="ok")])

    # Try to confirm a non-existent ID
    resp = client.post(
        "/api/confirm",
        json={"id": "non-existent-id", "approve": True},
        headers={"X-CoreCoder-Token": TOKEN},
    )
    assert resp.status_code == 404


def test_get_session_pending_returns_null_when_none():
    """GET /api/session/pending returns null when no confirmation pending."""
    client = _make_client([LLMResponse(content="ok")])

    resp = client.get(
        "/api/session/pending",
        params={"token": TOKEN},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending"] is None


def test_get_session_pending_returns_payload_when_waiting():
    """GET /api/session/pending returns full payload of pending confirmation."""
    from corecoder.web.confirm_registry import registry
    import threading

    client = _make_client([LLMResponse(content="ok")])

    # Create a pending confirmation with payload
    payload = {
        "action": "bash",
        "command": "rm -rf /",
        "reason": "force recursive delete",
    }
    event_id = registry.create(payload=payload)

    # Query the endpoint (in a thread to avoid blocking on wait())
    def resolve_later():
        import time
        time.sleep(0.5)
        registry.resolve(event_id, approve=False)

    thread = threading.Thread(target=resolve_later, daemon=True)
    thread.start()

    resp = client.get(
        "/api/session/pending",
        params={"token": TOKEN},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending"] is not None
    assert data["pending"]["id"] == event_id
    assert data["pending"]["action"] == "bash"
    assert data["pending"]["command"] == "rm -rf /"
    assert data["pending"]["reason"] == "force recursive delete"

    # Clean up: wait for the resolver thread
    thread.join(timeout=2)

