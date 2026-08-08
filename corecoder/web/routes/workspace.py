"""Workspace routes: file tree and file read API."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..workspace_fs import safe_read_dir, safe_read_dir_recursive, safe_read_file

router = APIRouter()


@router.get("/api/tree")
async def get_tree(path: str = Query(default=".")) -> JSONResponse:
    """List directory contents (for file tree sidebar).

    Query params:
    - path: directory path relative to workspace (default ".")

    Returns {entries: [{name, type, path}, ...]} on success.
    Returns {error: "..."} on failure.
    """
    success, entries, error = safe_read_dir(path)
    if not success:
        return JSONResponse({"error": error}, status_code=400)
    return JSONResponse({"entries": entries})


@router.get("/api/files")
async def get_files(path: str = Query(default=".")) -> JSONResponse:
    """List all files recursively (for autocomplete / file picker).

    Query params:
    - path: directory path relative to workspace (default ".")

    Returns {files: ["path/to/file", ...]} on success.
    Returns {error: "..."} on failure.
    """
    success, files, error = safe_read_dir_recursive(path)
    if not success:
        return JSONResponse({"error": error}, status_code=400)
    return JSONResponse({"files": files})


@router.get("/api/file")
async def get_file(path: str = Query(...)) -> JSONResponse:
    """Read file contents (for file preview/diff viewer).

    Query params:
    - path: file path relative to workspace (required)

    Returns {content: "..."} on success.
    Returns {error: "..."} on failure.
    """
    success, content, error = safe_read_file(path)
    if not success:
        return JSONResponse({"error": error}, status_code=400)
    return JSONResponse({"content": content})
