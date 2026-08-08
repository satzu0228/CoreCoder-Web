"""Workspace-scoped conversation persistence for the Web UI."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..agent import Agent
from ..tools.agent import AgentTool


WEB_SESSIONS_DIR = Path.home() / ".corecoder" / "web-sessions"
_VALID_SESSION_ID = set("0123456789abcdef")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _workspace_id(path: Path) -> str:
    normalized = os.path.normcase(str(path.resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _title_from_messages(messages: list[dict]) -> str:
    for message in messages:
        if message.get("role") == "user" and message.get("content"):
            title = " ".join(str(message["content"]).split())
            return title[:48] + ("…" if len(title) > 48 else "")
    return "新对话"


@dataclass
class WebSession:
    id: str
    workspace_id: str
    title: str
    model: str
    created_at: str
    updated_at: str
    status: str
    agent: Agent

    def summary(self) -> dict:
        preview = ""
        for message in self.agent.messages:
            if message.get("role") == "user" and message.get("content"):
                preview = " ".join(str(message["content"]).split())[:88]
                break
        return {
            "id": self.id,
            "title": self.title,
            "preview": preview,
            "model": self.model,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WebSessionManager:
    """Owns Web conversations for one workspace and serializes agent runs."""

    def __init__(
        self,
        prototype_agent: Agent,
        workspace_root: Path | None = None,
        storage_root: Path | None = None,
    ):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.workspace_id = _workspace_id(self.workspace_root)
        self.workspace_name = self.workspace_root.name or str(self.workspace_root)
        self.storage_root = storage_root
        self.session_dir = storage_root / self.workspace_id if storage_root is not None else None
        self._prototype = prototype_agent
        self._prototype_claimed = False
        self._sessions: dict[str, WebSession] = {}
        self._lock = threading.RLock()
        self.running_session_id: str | None = None
        self._cancel_events: dict[str, threading.Event] = {}
        self._load()

        # Preserve a pre-populated Agent supplied by callers such as tests or
        # an embedding application. Normal `corecoder web` starts empty.
        if prototype_agent.messages and not self._sessions:
            session = self._new_session(agent=prototype_agent)
            self._prototype_claimed = True
            self._sessions[session.id] = session

    def _new_agent(self) -> Agent:
        if not self._prototype_claimed:
            self._prototype_claimed = True
            return self._prototype
        return Agent(
            llm=self._prototype.llm,
            tools=self._prototype.tools,
            max_context_tokens=self._prototype.context.max_tokens,
            max_rounds=self._prototype.max_rounds,
        )

    def _new_session(self, agent: Agent | None = None) -> WebSession:
        now = _now()
        selected_agent = agent or self._new_agent()
        return WebSession(
            id=uuid.uuid4().hex,
            workspace_id=self.workspace_id,
            title=_title_from_messages(selected_agent.messages),
            model=getattr(selected_agent.llm, "model", "unknown"),
            created_at=now,
            updated_at=now,
            status="idle",
            agent=selected_agent,
        )

    def _path(self, session_id: str) -> Path:
        if len(session_id) != 32 or any(ch not in _VALID_SESSION_ID for ch in session_id):
            raise KeyError(session_id)
        if self.session_dir is None:
            raise RuntimeError("session persistence is disabled")
        return self.session_dir / f"{session_id}.json"

    def _load(self) -> None:
        if self.session_dir is None or not self.session_dir.exists():
            return
        for path in self.session_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("workspace_id") != self.workspace_id:
                    continue
                session_id = str(data["id"])
                self._path(session_id)
                agent = self._new_agent()
                messages = data.get("messages", [])
                if not isinstance(messages, list):
                    continue
                agent.messages = messages
                status = str(data.get("status", "idle"))
                if status in {"running", "waiting_confirmation"}:
                    status = "interrupted"
                self._sessions[session_id] = WebSession(
                    id=session_id,
                    workspace_id=self.workspace_id,
                    title=str(data.get("title") or _title_from_messages(messages)),
                    model=str(data.get("model") or getattr(agent.llm, "model", "unknown")),
                    created_at=str(data.get("created_at") or _now()),
                    updated_at=str(data.get("updated_at") or _now()),
                    status=status,
                    agent=agent,
                )
                if status == "interrupted":
                    self._persist(self._sessions[session_id])
            except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
                # One broken conversation must not hide the rest of the list.
                continue

    def _persist(self, session: WebSession) -> None:
        if self.session_dir is None:
            return
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(session.id)
        temporary = path.with_suffix(".json.tmp")
        data = {
            "version": 1,
            "id": session.id,
            "workspace_id": session.workspace_id,
            "title": session.title,
            "model": session.model,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "status": session.status,
            "messages": session.agent.messages,
        }
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def list(self) -> list[dict]:
        with self._lock:
            sessions = sorted(self._sessions.values(), key=lambda item: item.updated_at, reverse=True)
            return [session.summary() for session in sessions]

    def create(self) -> WebSession:
        with self._lock:
            session = self._new_session()
            self._sessions[session.id] = session
            self._persist(session)
            return session

    def ensure_default(self) -> WebSession:
        with self._lock:
            if self._sessions:
                return max(self._sessions.values(), key=lambda item: item.updated_at)
            return self.create()

    def get(self, session_id: str) -> WebSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError:
                raise KeyError(session_id) from None

    def rename(self, session_id: str, title: str) -> WebSession:
        title = " ".join(title.split()).strip()[:80]
        if not title:
            raise ValueError("title cannot be empty")
        with self._lock:
            session = self.get(session_id)
            session.title = title
            session.updated_at = _now()
            self._persist(session)
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            if self.running_session_id == session_id:
                raise RuntimeError("running session cannot be deleted")
            session = self.get(session_id)
            self._sessions.pop(session.id)
            if self.session_dir is not None:
                path = self._path(session.id)
                if path.exists():
                    path.unlink()

    def begin_run(self, session_id: str) -> WebSession:
        with self._lock:
            if self.running_session_id is not None:
                raise RuntimeError(self.running_session_id)
            session = self.get(session_id)
            self.running_session_id = session_id
            self._cancel_events[session_id] = threading.Event()
            session.status = "running"
            session.updated_at = _now()
            for tool in session.agent.tools:
                if isinstance(tool, AgentTool):
                    tool._parent_agent = session.agent
            self._persist(session)
            return session

    def cancel_event(self, session_id: str) -> threading.Event | None:
        """Return the cancel Event for the given session, or None."""
        with self._lock:
            return self._cancel_events.get(session_id)

    def cancel_run(self, session_id: str) -> bool:
        """Signal cancellation for a running session. Returns True if found."""
        with self._lock:
            ev = self._cancel_events.get(session_id)
            if ev is None:
                return False
            ev.set()
            return True

    def set_status(self, session_id: str, status: str, persist: bool = True) -> None:
        with self._lock:
            session = self.get(session_id)
            session.status = status
            session.updated_at = _now()
            if persist:
                self._persist(session)

    def finish_run(self, session_id: str, status: str = "idle") -> None:
        with self._lock:
            session = self.get(session_id)
            if session.title == "新对话":
                session.title = _title_from_messages(session.agent.messages)
            session.status = status
            session.updated_at = _now()
            if self.running_session_id == session_id:
                self.running_session_id = None
            self._cancel_events.pop(session_id, None)
            self._persist(session)
