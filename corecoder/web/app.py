"""FastAPI app factory: wires the Agent instance, token auth, and routes."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from ..agent import Agent
from .routes.chat import router as chat_router

_STATIC_DIR = Path(__file__).parent / "static"

# paths that don't require the auth token (the SPA shell itself has to load
# before it can read the token out of its own URL)
_PUBLIC_PATHS = {"/"}


def create_app(agent: Agent, token: str) -> FastAPI:
    app = FastAPI(title="CoreCoder Web")
    app.state.agent = agent
    app.state.token = token

    @app.middleware("http")
    async def check_token(request: Request, call_next):
        if request.url.path not in _PUBLIC_PATHS:
            supplied = request.headers.get("x-corecoder-token") or request.query_params.get("token")
            if supplied != request.app.state.token:
                return JSONResponse({"error": "invalid or missing token"}, status_code=403)
        return await call_next(request)

    @app.get("/")
    async def index():
        return FileResponse(_STATIC_DIR / "index.html")

    app.include_router(chat_router)
    return app
