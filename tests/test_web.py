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
