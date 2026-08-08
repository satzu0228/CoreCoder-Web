"""Boots the Web server: pick a free port, start uvicorn in a thread, open
the browser once it's actually accepting connections, then block until the
user hits Ctrl+C.
"""

import secrets
import socket
import threading
import time
import webbrowser

import uvicorn

from ..agent import Agent
from .app import create_app
from .web_sessions import WEB_SESSIONS_DIR


def _pick_free_port() -> int:
    """Ask the OS for a free localhost port.

    There's a small window between closing this probe socket and uvicorn
    binding its own - acceptable for a local single-user dev server (the
    same approach Jupyter uses), not something we'd do for a shared host.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_web(agent: Agent) -> int:
    """Start the Web server bound to the current workspace. Blocks until Ctrl+C."""
    port = _pick_free_port()
    token = secrets.token_urlsafe(16)
    app = create_app(agent, token, session_storage_root=WEB_SESSIONS_DIR)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started and thread.is_alive():
        time.sleep(0.05)

    if not thread.is_alive():
        print("CoreCoder Web failed to start.")
        return 1

    url = f"http://127.0.0.1:{port}/?token={token}"
    print(f"CoreCoder Web running at {url}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url)

    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=5)
        print("\nStopped.")
    return 0
