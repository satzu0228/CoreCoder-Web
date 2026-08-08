"""FastAPI app factory: wires the Agent instance, token auth, and routes."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..agent import Agent
from .routes.chat import router as chat_router
from .routes.confirm import router as confirm_router
from .routes.session import router as session_router
from .routes.workspace import router as workspace_router

_STATIC_DIR = Path(__file__).parent / "static"
_DIST_DIR = _STATIC_DIR / "dist"

# paths that don't require the auth token (the SPA shell itself has to load
# before it can read the token out of its own URL)
_PUBLIC_PATHS = {"/", "/index.html"}


def create_app(agent: Agent, token: str) -> FastAPI:
    app = FastAPI(title="CoreCoder Web")
    app.state.agent = agent
    app.state.token = token

    @app.middleware("http")
    async def check_token(request: Request, call_next):
        # API routes need token; static files and public paths don't
        path = request.url.path

        # Whitelist static file extensions (Vue build output)
        static_extensions = ('.js', '.css', '.svg', '.woff', '.woff2', '.ttf', '.eot', '.map', '.json')
        if any(path.endswith(ext) for ext in static_extensions):
            return await call_next(request)

        # API routes need token
        if path.startswith("/api/"):
            supplied = request.headers.get("x-corecoder-token") or request.query_params.get("token")
            if supplied != request.app.state.token:
                return JSONResponse({"error": "invalid or missing token"}, status_code=403)

        return await call_next(request)

    @app.get("/")
    async def index():
        # Source checkouts remain usable before the Vue build; release builds
        # include dist/ and therefore serve the full frontend.
        built_index = _DIST_DIR / "index.html"
        return FileResponse(built_index if built_index.exists() else _STATIC_DIR / "index.html")

    app.include_router(chat_router)
    app.include_router(confirm_router)
    app.include_router(session_router)
    app.include_router(workspace_router)

    # Serve static assets from dist/ (CSS, JS, etc.)
    # Must be mounted last so route handlers take precedence
    if _DIST_DIR.exists():
        app.mount("/", StaticFiles(directory=_DIST_DIR, html=True), name="static")

    return app
