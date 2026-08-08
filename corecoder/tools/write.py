"""File creation / overwrite."""

from ..web import events
from ..web._confirmable import request_confirmation
from ..web.confirm_registry import ConfirmResult
from ..web.workspace_fs import resolve_tool_path
from .base import Tool
from .edit import _changed_files, _unified_diff


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Create a new file or completely overwrite an existing one. "
        "For small edits to existing files, prefer edit_file instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path for the file",
            },
            "content": {
                "type": "string",
                "description": "Full file content to write",
            },
        },
        "required": ["file_path", "content"],
    }

    def execute(self, file_path: str, content: str) -> str:
        try:
            p, path_error = resolve_tool_path(file_path, restrict_to_workspace=events.has_emitter())
            if p is None:
                return f"Error: {path_error}"
            old_content = ""
            if p.exists():
                if not p.is_file():
                    return f"Error: {file_path} is not a file"
                try:
                    old_content = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    return f"Error: {file_path} is not a UTF-8 text file"

            if events.has_emitter():
                diff = _unified_diff(old_content, content, str(p))
                result = request_confirmation(
                    "write_file",
                    {
                        "file_path": file_path,
                        "diff": diff,
                        "old_content": old_content,
                        "new_content": content,
                    },
                )
                if result == ConfirmResult.REJECTED:
                    return f"User explicitly rejected this write.\nFile: {file_path}"
                if result == ConfirmResult.TIMEOUT:
                    return f"Write confirmation timeout (300s). User did not respond.\nFile: {file_path}"

            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            _changed_files.add(str(p))
            n_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return f"Wrote {n_lines} lines to {file_path}"
        except Exception as e:
            return f"Error: {e}"
