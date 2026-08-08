"""Content search with regex support."""

import re
from pathlib import Path

from ..web import events
from ..web.workspace_fs import resolve_tool_path
from .base import Tool

# skip these dirs to avoid noise
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}


class GrepTool(Tool):
    name = "grep"
    description = (
        "Search file contents with regex. "
        "Returns matching lines with file path and line number."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search (default: cwd)",
            },
            "include": {
                "type": "string",
                "description": "Only search files matching this glob (e.g. '*.py')",
            },
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = ".", include: str | None = None) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"

        base, path_error = resolve_tool_path(path, restrict_to_workspace=events.has_emitter())
        if base is None:
            return f"Error: {path_error}"
        if not base.exists():
            return f"Error: {path} not found"

        if base.is_file():
            files = [base]
        else:
            files = self._walk(base, include)

        matches = []
        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    matches.append(f"{fp}:{lineno}: {line.rstrip()}")
                    if len(matches) >= 200:
                        matches.append("... (200 match limit reached)")
                        return "\n".join(matches)

        return "\n".join(matches) if matches else "No matches found."

    @staticmethod
    def _walk(root: Path, include: str | None) -> list[Path]:
        """Walk dir tree, skipping junk dirs."""
        results = []
        for item in root.rglob(include or "*"):
            # skip junk dirs *inside* the search root - matching item.parts would
            # also catch an ancestor named e.g. "build" and hide the whole tree
            if any(part in _SKIP_DIRS for part in item.relative_to(root).parts):
                continue
            if item.is_file():
                results.append(item)
            if len(results) >= 5000:
                break
        return results
