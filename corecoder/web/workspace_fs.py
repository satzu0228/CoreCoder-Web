"""Workspace filesystem utilities: path safety validation."""

from pathlib import Path


def get_workspace_root() -> Path:
    """Get the current workspace root (where the agent was started)."""
    return Path.cwd().resolve()


def resolve_tool_path(requested_path: str, *, restrict_to_workspace: bool) -> tuple[Path | None, str]:
    """Resolve a tool path and optionally enforce the Web workspace boundary."""
    if not restrict_to_workspace:
        return Path(requested_path).expanduser().resolve(), ""
    valid, resolved, error = validate_path(requested_path)
    return (resolved, "") if valid else (None, error)


def validate_path(requested_path: str) -> tuple[bool, Path | None, str]:
    """Validate that a requested path is safe and within workspace.

    Returns (is_valid, resolved_path, error_message).
    - is_valid: True if path is safe and within workspace
    - resolved_path: Resolved absolute Path if valid, None otherwise
    - error_message: Human-readable error if not valid, empty string if valid
    """
    try:
        # Convert to Path and resolve relative to workspace
        ws_root = get_workspace_root()
        requested = Path(requested_path)

        # If absolute, use as-is; if relative, treat as relative to workspace
        if requested.is_absolute():
            resolved = requested.resolve()
        else:
            resolved = (ws_root / requested).resolve()

        # Check path traversal: resolved path must be within or equal to workspace
        try:
            # is_relative_to checks if resolved is a subpath of ws_root
            resolved.relative_to(ws_root)
        except ValueError:
            # Path is outside workspace
            return False, None, f"Path traversal detected: {requested_path} is outside workspace"

        # Path is valid
        return True, resolved, ""

    except Exception as e:
        return False, None, f"Invalid path: {e}"


def safe_read_dir(requested_path: str) -> tuple[bool, list[dict] | None, str]:
    """Safely list directory contents.

    Returns (success, entries, error_message).
    entries: list of {name, type} dicts where type is 'dir' or 'file'.
    """
    is_valid, resolved, error = validate_path(requested_path)
    if not is_valid:
        return False, None, error

    try:
        if not resolved.is_dir():
            return False, None, f"Not a directory: {requested_path}"

        entries = []
        for item in sorted(resolved.iterdir()):
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "path": str(item.relative_to(get_workspace_root())),
            })
        return True, entries, ""

    except PermissionError:
        return False, None, f"Permission denied: {requested_path}"
    except Exception as e:
        return False, None, f"Error reading directory: {e}"


def safe_read_file(requested_path: str, max_size: int = 1_000_000) -> tuple[bool, str | None, str]:
    """Safely read file contents (up to max_size).

    Returns (success, content, error_message).
    """
    is_valid, resolved, error = validate_path(requested_path)
    if not is_valid:
        return False, None, error

    try:
        if not resolved.is_file():
            return False, None, f"Not a file: {requested_path}"

        size = resolved.stat().st_size
        if size > max_size:
            return False, None, f"File too large ({size} bytes, limit {max_size})"

        content = resolved.read_text(encoding="utf-8")
        return True, content, ""

    except UnicodeDecodeError:
        return False, None, f"File is not UTF-8: {requested_path}"
    except PermissionError:
        return False, None, f"Permission denied: {requested_path}"
    except Exception as e:
        return False, None, f"Error reading file: {e}"
