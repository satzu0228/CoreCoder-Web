"""Tests for the FastAPI Web layer: token auth and the SSE chat stream.

Uses ScriptedLLM so no real API key or network call is needed.
"""

import json
import threading
import time

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
    assert events[-1]["type"] == "done"
    assert events[-1]["status"] == "idle"
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
    assert events[-1]["type"] == "done"
    assert events[-1]["status"] == "error"
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
    assert events[-1]["type"] == "done"
    assert events[-1]["status"] == "idle"

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


def test_web_edit_waits_for_approval_before_writing(tmp_path, monkeypatch):
    """Web edit_file must not touch disk until the confirmation is approved."""
    from corecoder.tools.edit import EditFileTool
    from corecoder.web import events
    from corecoder.web.confirm_registry import registry

    path = tmp_path / "sample.py"
    path.write_text("answer = 41\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    emitted = []
    result = []
    events.set_emitter(lambda event_type, data: emitted.append((event_type, data)))
    worker = threading.Thread(
        target=lambda: result.append(EditFileTool().execute("sample.py", "41", "42")),
        daemon=True,
    )
    try:
        worker.start()
        deadline = time.monotonic() + 2
        while not emitted and time.monotonic() < deadline:
            time.sleep(0.01)

        assert emitted and emitted[0][0] == "confirm_required"
        assert path.read_text(encoding="utf-8") == "answer = 41\n"
        assert registry.resolve(emitted[0][1]["id"], approve=True)
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert "Edited" in result[0]
        assert path.read_text(encoding="utf-8") == "answer = 42\n"
    finally:
        events.clear_emitter()


def test_parallel_confirmations_are_emitted_one_at_a_time():
    """The single-modal MVP serializes parallel confirmation requests."""
    from corecoder.web import events
    from corecoder.web._confirmable import request_confirmation
    from corecoder.web.confirm_registry import ConfirmResult, registry

    emitted = []
    results = []
    events.set_emitter(lambda event_type, data: emitted.append((event_type, data)))
    workers = [
        threading.Thread(
            target=lambda name=name: results.append(
                request_confirmation("bash", {"command": name, "reason": "test"}, timeout=2)
            ),
            daemon=True,
        )
        for name in ("first", "second")
    ]
    try:
        for worker in workers:
            worker.start()

        deadline = time.monotonic() + 2
        while len(emitted) < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(emitted) == 1
        assert registry.resolve(emitted[0][1]["id"], approve=True)

        deadline = time.monotonic() + 2
        while len(emitted) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(emitted) == 2
        assert registry.resolve(emitted[1][1]["id"], approve=True)

        for worker in workers:
            worker.join(timeout=2)
        assert results == [ConfirmResult.APPROVED, ConfirmResult.APPROVED]
    finally:
        events.clear_emitter()


def test_web_write_requires_confirmation_and_reject_keeps_disk_unchanged(tmp_path, monkeypatch):
    """write_file cannot bypass the Web approval flow by overwriting a file."""
    from corecoder.tools.write import WriteFileTool
    from corecoder.web import events
    from corecoder.web.confirm_registry import registry

    path = tmp_path / "notes.txt"
    path.write_text("original\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    emitted = []
    result = []
    events.set_emitter(lambda event_type, data: emitted.append((event_type, data)))
    worker = threading.Thread(
        target=lambda: result.append(WriteFileTool().execute("notes.txt", "replacement\n")),
        daemon=True,
    )
    try:
        worker.start()
        deadline = time.monotonic() + 2
        while not emitted and time.monotonic() < deadline:
            time.sleep(0.01)

        assert emitted[0][1]["action"] == "write_file"
        assert path.read_text(encoding="utf-8") == "original\n"
        assert registry.resolve(emitted[0][1]["id"], approve=False)
        worker.join(timeout=2)
        assert "explicitly rejected" in result[0]
        assert path.read_text(encoding="utf-8") == "original\n"
    finally:
        events.clear_emitter()


def test_web_file_tool_rejects_path_outside_workspace(tmp_path, monkeypatch):
    from corecoder.tools.read import ReadFileTool
    from corecoder.web import events

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.chdir(workspace)
    events.set_emitter(lambda *_: None)
    try:
        result = ReadFileTool().execute(str(outside))
        assert "outside workspace" in result
    finally:
        events.clear_emitter()


def test_session_messages_returns_ui_dto_with_completed_tool_calls():
    agent = Agent(llm=ScriptedLLM([]), tools=[])
    agent.messages = [
        {"role": "user", "content": "inspect"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"file_path":"README.md"}'},
            }],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "1\t# CoreCoder"},
        {"role": "assistant", "content": "Done."},
    ]
    client = TestClient(create_app(agent, TOKEN))

    resp = client.get("/api/session/messages", headers={"X-CoreCoder-Token": TOKEN})

    assert resp.status_code == 200
    assert resp.json()["running"] is False
    messages = resp.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Done."
    assert messages[1]["toolCalls"] == [{
        "id": "call-1",
        "name": "read_file",
        "args": {"file_path": "README.md"},
        "status": "done",
        "result": "1\t# CoreCoder",
    }]


def test_session_messages_marks_unanswered_tool_call_running():
    agent = Agent(llm=ScriptedLLM([]), tools=[])
    agent.messages = [{
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "pending",
            "type": "function",
            "function": {"name": "edit_file", "arguments": "not-json"},
        }],
    }]
    app = create_app(agent, TOKEN)
    app.state.agent_running = True

    resp = TestClient(app).get("/api/session/messages", headers={"X-CoreCoder-Token": TOKEN})

    assert resp.status_code == 200
    assert resp.json()["running"] is True
    tool_call = resp.json()["messages"][0]["toolCalls"][0]
    assert tool_call["status"] == "running"
    assert tool_call["args"] == {"raw": "not-json"}


def test_web_sessions_are_persisted_and_restored_for_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    storage = tmp_path / "sessions"
    workspace.mkdir()
    headers = {"X-CoreCoder-Token": TOKEN}

    first_agent = Agent(llm=ScriptedLLM([LLMResponse(content="persisted reply")]), tools=[])
    first_app = create_app(
        first_agent,
        TOKEN,
        workspace_root=workspace,
        session_storage_root=storage,
    )
    first_client = TestClient(first_app)

    created = first_client.post("/api/sessions", headers=headers)
    assert created.status_code == 201
    session_id = created.json()["session"]["id"]
    response = first_client.post(
        f"/api/sessions/{session_id}/chat",
        json={"message": "remember this"},
        headers=headers,
    )
    assert response.status_code == 200
    done = _parse_sse(response.text)[-1]
    assert done["type"] == "done"
    assert done["status"] == "idle"
    assert done["session_id"] == session_id

    restored_app = create_app(
        Agent(llm=ScriptedLLM([]), tools=[]),
        TOKEN,
        workspace_root=workspace,
        session_storage_root=storage,
    )
    restored_client = TestClient(restored_app)
    listing = restored_client.get("/api/sessions", headers=headers).json()
    assert [item["id"] for item in listing["sessions"]] == [session_id]
    assert listing["sessions"][0]["title"] == "remember this"

    detail = restored_client.get(f"/api/sessions/{session_id}", headers=headers).json()
    assert [message["content"] for message in detail["messages"]] == ["remember this", "persisted reply"]


def test_web_sessions_are_isolated_by_workspace(tmp_path):
    storage = tmp_path / "sessions"
    workspace_a = tmp_path / "alpha"
    workspace_b = tmp_path / "beta"
    workspace_a.mkdir()
    workspace_b.mkdir()
    headers = {"X-CoreCoder-Token": TOKEN}

    app_a = create_app(
        Agent(llm=ScriptedLLM([]), tools=[]), TOKEN,
        workspace_root=workspace_a, session_storage_root=storage,
    )
    assert TestClient(app_a).post("/api/sessions", headers=headers).status_code == 201

    app_b = create_app(
        Agent(llm=ScriptedLLM([]), tools=[]), TOKEN,
        workspace_root=workspace_b, session_storage_root=storage,
    )
    listing = TestClient(app_b).get("/api/sessions", headers=headers).json()
    assert listing["workspace"]["name"] == "beta"
    assert listing["sessions"] == []


def test_web_session_crud_and_single_run_lock(tmp_path):
    app = create_app(
        Agent(llm=ScriptedLLM([]), tools=[]), TOKEN,
        workspace_root=tmp_path, session_storage_root=tmp_path / "sessions",
    )
    client = TestClient(app)
    headers = {"X-CoreCoder-Token": TOKEN}
    first = client.post("/api/sessions", headers=headers).json()["session"]
    second = client.post("/api/sessions", headers=headers).json()["session"]

    renamed = client.patch(
        f"/api/sessions/{first['id']}", json={"title": "Architecture review"}, headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["session"]["title"] == "Architecture review"

    app.state.sessions.begin_run(first["id"])
    blocked = client.post(
        f"/api/sessions/{second['id']}/chat", json={"message": "hello"}, headers=headers,
    )
    assert blocked.status_code == 409
    assert client.delete(f"/api/sessions/{first['id']}", headers=headers).status_code == 409
    app.state.sessions.finish_run(first["id"], "interrupted")

    assert client.delete(f"/api/sessions/{first['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/sessions/{first['id']}", headers=headers).status_code == 404


def test_corrupt_web_session_does_not_hide_valid_sessions(tmp_path):
    storage = tmp_path / "sessions"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    headers = {"X-CoreCoder-Token": TOKEN}
    app = create_app(
        Agent(llm=ScriptedLLM([]), tools=[]), TOKEN,
        workspace_root=workspace, session_storage_root=storage,
    )
    client = TestClient(app)
    valid = client.post("/api/sessions", headers=headers).json()["session"]
    session_dir = app.state.sessions.session_dir
    (session_dir / ("f" * 32 + ".json")).write_text("{broken", encoding="utf-8")

    restored = create_app(
        Agent(llm=ScriptedLLM([]), tools=[]), TOKEN,
        workspace_root=workspace, session_storage_root=storage,
    )
    listing = TestClient(restored).get("/api/sessions", headers=headers).json()["sessions"]
    assert [item["id"] for item in listing] == [valid["id"]]
