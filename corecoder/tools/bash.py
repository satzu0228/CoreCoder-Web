"""Shell command execution with safety checks.

Claude Code's BashTool is 1,143 lines. This is the distilled version:
- Output capture with truncation (head+tail preserved)
- Timeout support
- Dangerous command detection
- Working directory tracking (cd awareness)
"""

import os
import platform
import re
import signal
import subprocess
import threading
from .base import Tool

# Import confirmation helpers; only used when a Web SSE emitter is active.
try:
    from ..web._confirmable import request_confirmation
    from ..web.confirm_registry import ConfirmResult
    from ..web import events as web_events
except ImportError:
    request_confirmation = None
    ConfirmResult = None
    web_events = None

# Track cwd across commands (Claude Code does this too). Thread-local, so that
# when the agent executes tools in parallel two bash calls never race on one
# shared global: each worker thread carries its own cwd. See article 05.
_local = threading.local()

# Track the currently running subprocess so the cancel flow can terminate it.
# Protected by _proc_lock; cleared when the process exits naturally.
_current_process: subprocess.Popen | None = None
_proc_lock = threading.Lock()


def cancel_current_command() -> bool:
    """Kill the currently running bash subprocess (if any). Returns True if killed."""
    with _proc_lock:
        proc = _current_process
    if proc is None:
        return False
    try:
        pid = proc.pid
        if platform.system() == "Windows":
            # Terminate entire process tree on Windows
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
            )
        else:
            # Send SIGTERM to the process group on Unix
            try:
                os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        proc.kill()
        return True
    except Exception:
        return False


def _set_current_process(proc: subprocess.Popen | None) -> None:
    with _proc_lock:
        global _current_process
        _current_process = proc


# patterns that could wreck the filesystem or leak secrets
_DANGEROUS_PATTERNS = [
    # recursive delete aimed at root/home (force flag optional)
    (r"\brm\s+(-\w*)?-r\w*\s+(/|~|\$HOME)", "recursive delete on home/root"),
    # recursive (-r/-R) and force (-f) flags together, in any order or spacing
    (r"\brm\b(?=(?:.*\s)?-\w*[rR])(?=(?:.*\s)?-\w*f)", "force recursive delete"),
    # the same, written with long-form flags
    (r"\brm\b.*--recursive\b.*--force\b|\brm\b.*--force\b.*--recursive\b", "force recursive delete"),
    (r"\bmkfs\b", "format filesystem"),
    (r"\bdd\s+.*of=/dev/", "raw disk write"),
    (r">\s*/dev/sd[a-z]", "overwrite block device"),
    (r"\bchmod\s+(-R\s+)?777\s+/", "chmod 777 on root"),
    (r":\(\)\s*\{.*:\|:.*\}", "fork bomb"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?(ba)?sh\b", "pipe curl to shell"),
    (r"\bwget\b.*\|\s*(sudo\s+)?(ba)?sh\b", "pipe wget to shell"),
]


class BashTool(Tool):
    name = "bash"
    description = (
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "Use this for running tests, installing packages, git operations, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to run",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 120)",
            },
        },
        "required": ["command"],
    }

    def execute(self, command: str, timeout: int = 120) -> str:
        # safety check
        warning = _check_dangerous(command)
        if warning:
            # Web mode: request user confirmation; CLI mode: direct reject
            if web_events and web_events.has_emitter():
                # Web mode: emit confirmation request and wait for user response
                result = request_confirmation(
                    "bash",
                    {"command": command, "reason": warning},
                )

                if result == ConfirmResult.APPROVED:
                    # User approved; continue to execute the command below
                    pass
                elif result == ConfirmResult.REJECTED:
                    return f"User explicitly rejected this command.\nCommand: {command}\nReason: {warning}\n\nPlease ask the user for clarification or suggest a safer alternative."
                else:  # ConfirmResult.TIMEOUT
                    return f"Command confirmation timeout (300s). User did not respond.\nCommand: {command}\nReason: {warning}"
            else:
                # CLI mode or events not initialized: direct reject (backward compatible)
                return f"⚠ Blocked: {warning}\nCommand: {command}\nIf intentional, modify the command to be more specific."

        # use this thread's own tracked working directory
        cwd = getattr(_local, "cwd", None) or os.getcwd()

        # Use Popen with process group so cancel can terminate the entire tree.
        popen_kwargs: dict = {
            "shell": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "cwd": cwd,
        }
        if platform.system() == "Windows":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["preexec_fn"] = os.setpgrp

        try:
            proc = subprocess.Popen(**popen_kwargs)
            _set_current_process(proc)
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            finally:
                _set_current_process(None)

            # track cd commands so next command runs in the right place
            if proc.returncode == 0:
                _update_cwd(command, cwd)
            out = stdout
            if stderr:
                out += f"\n[stderr]\n{stderr}"
            if proc.returncode != 0:
                out += f"\n[exit code: {proc.returncode}]"
            # keep head + tail to preserve the most useful info
            if len(out) > 15_000:
                out = (
                    out[:6000]
                    + f"\n\n... truncated ({len(out)} chars total) ...\n\n"
                    + out[-3000:]
                )
            return out.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            _set_current_process(None)
            try:
                if platform.system() == "Windows":
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=10)
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            return f"Error: timed out after {timeout}s"
        except Exception as e:
            _set_current_process(None)
            return f"Error running command: {e}"


def _check_dangerous(cmd: str) -> str | None:
    """Return a warning string if the command looks destructive, else None."""
    for pattern, reason in _DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return reason
    return None


def _update_cwd(command: str, current_cwd: str):
    """Track directory changes from cd commands, per thread."""
    # walk each cd in a && chain, resolving relative targets against the dir the
    # previous cd landed in (not the original cwd) so `cd a && cd b` ends in a/b
    running = current_cwd
    changed = False
    for part in command.split("&&"):
        part = part.strip()
        if part.startswith("cd "):
            target = part[3:].strip().strip("'\"")
            if target:
                new_dir = os.path.normpath(os.path.join(running, os.path.expanduser(target)))
                if os.path.isdir(new_dir):
                    running = new_dir
                    changed = True
    if changed:
        _local.cwd = running
