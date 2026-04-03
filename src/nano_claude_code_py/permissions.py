from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from nano_claude_code_py.tools.base import Tool


PermissionMode = str
PromptFn = Callable[[str], bool]

LEGACY_PERMISSION_MODE_ALIASES: dict[str, str] = {
    "ask": "default",
    "danger-full-access": "bypassPermissions",
    "auto-allow-read": "dontAsk",
}

VALID_PERMISSION_MODES = {
    "acceptEdits",
    "bypassPermissions",
    "default",
    "dontAsk",
    "plan",
}

WRITE_PERMISSION_TOOL_NAMES = {"Edit", "Write", "NotebookEdit"}
NO_PERMISSION_TOOL_NAMES = {"TodoWrite"}
DENIAL_WORKAROUND_GUIDANCE = (
    "IMPORTANT: You may attempt to accomplish this action using other tools "
    "that might naturally be used to accomplish this goal, but you should "
    "not attempt to work around this denial in malicious ways. If you "
    "believe this capability is essential to complete the user's request, "
    "STOP and explain to the user what you were trying to do and why you "
    "need this permission. Let the user decide how to proceed."
)


@dataclass
class PermissionManager:
    mode: PermissionMode = "default"
    prompt: PromptFn | None = None

    def allow(
        self,
        tool: Tool,
        summary: str,
        *,
        args: BaseModel | None = None,
        cwd: Path | None = None,
    ) -> bool:
        mode = normalize_permission_mode(self.mode)
        is_readonly = tool_is_readonly(tool, args)

        if tool.name in NO_PERMISSION_TOOL_NAMES:
            return True

        if mode == "bypassPermissions":
            return True
        if mode in {"dontAsk", "plan"}:
            return is_readonly
        if mode == "acceptEdits":
            if tool.name in WRITE_PERMISSION_TOOL_NAMES:
                if tool_targets_working_dir(tool.name, args, cwd):
                    return True
                if self.prompt is None:
                    return False
                return self.prompt(summary)
            return is_readonly or tool.name in WRITE_PERMISSION_TOOL_NAMES
        if mode != "default":
            return False
        if is_readonly:
            return True
        if self.prompt is None:
            return False
        return self.prompt(summary)


def summarize_tool_request(
    tool: Tool,
    arguments: dict[str, object],
    *,
    args: BaseModel | None = None,
) -> str:
    access = "read-only" if tool_is_readonly(tool, args) else "write/exec"
    summary = tool_request_summary(tool.name, arguments)
    return f"{tool.name} [{access}] {summary}"


def permission_denial_message(
    manager: PermissionManager,
    tool: Tool,
    summary: str,
) -> str:
    mode = normalize_permission_mode(manager.mode)
    if mode == "dontAsk":
        return (
            f"Permission to use {tool.name} has been denied because Claude "
            f"Code is running in don't ask mode. {DENIAL_WORKAROUND_GUIDANCE}"
        )
    if mode == "default" and manager.prompt is None:
        return (
            f"Permission to use {tool.name} has been denied. "
            f"{DENIAL_WORKAROUND_GUIDANCE}"
        )
    return f"Permission denied for: {summary}"


def tool_is_readonly(tool: Tool, args: BaseModel | None = None) -> bool:
    readonly_for_args = getattr(tool, "is_readonly_args", None)
    if callable(readonly_for_args):
        return bool(readonly_for_args(args))
    return tool.is_readonly


def normalize_permission_mode(mode: str) -> str:
    normalized = LEGACY_PERMISSION_MODE_ALIASES.get(mode, mode)
    if normalized in VALID_PERMISSION_MODES:
        return normalized
    return "default"


def tool_targets_working_dir(
    tool_name: str,
    args: BaseModel | None,
    cwd: Path | None,
) -> bool:
    if cwd is None:
        return False

    path_value = tool_path_argument(tool_name, args)
    if not path_value:
        return False

    try:
        target = Path(path_value)
        if not target.is_absolute():
            target = cwd / target
        target = target.resolve(strict=False)
        workspace = cwd.resolve(strict=False)
        target.relative_to(workspace)
    except Exception:
        return False
    return True


def tool_path_argument(tool_name: str, args: BaseModel | None) -> str | None:
    if args is None:
        return None
    if tool_name in {"Read", "Write", "Edit"}:
        value = getattr(args, "file_path", None)
        return value if isinstance(value, str) else None
    if tool_name == "NotebookEdit":
        value = getattr(args, "notebook_path", None)
        return value if isinstance(value, str) else None
    return None


def tool_request_summary(tool_name: str, arguments: dict[str, object]) -> str:
    if tool_name == "Read":
        path = arguments.get("file_path")
        if isinstance(path, str) and path:
            parts = [path]
            pages = arguments.get("pages")
            if isinstance(pages, str) and pages:
                parts.append(f"pages {pages}")
            else:
                offset = arguments.get("offset")
                limit = arguments.get("limit")
                line_summary = summarize_read_lines(offset, limit)
                if line_summary is not None:
                    parts.append(line_summary)
            return " · ".join(parts)
    if tool_name in {"Write", "Edit"}:
        path = arguments.get("file_path")
        if isinstance(path, str) and path:
            return path
    if tool_name == "NotebookEdit":
        path = arguments.get("notebook_path")
        if isinstance(path, str) and path:
            return path
    if tool_name in {"Glob", "Grep"}:
        pattern = arguments.get("pattern")
        if isinstance(pattern, str) and pattern:
            parts = [f'pattern: "{pattern}"']
            path = arguments.get("path")
            if isinstance(path, str) and path and path != ".":
                parts.append(f'path: "{path}"')
            return truncate_tool_summary(", ".join(parts))
    if tool_name == "TodoWrite":
        todos = arguments.get("todos")
        if isinstance(todos, list):
            return f"{len(todos)} items"
    if tool_name == "Bash":
        description = arguments.get("description")
        if isinstance(description, str) and description:
            return description
        command = arguments.get("command")
        if isinstance(command, str) and command:
            return truncate_tool_summary(command)

    serialized = json.dumps(arguments, ensure_ascii=True, sort_keys=True)
    if len(serialized) > 180:
        serialized = serialized[:177] + "..."
    return serialized


def truncate_tool_summary(value: str, limit: int = 50) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def summarize_read_lines(
    offset: object,
    limit: object,
) -> str | None:
    if offset == 0 and limit is None:
        return None
    if not isinstance(offset, int):
        return None
    first_line = offset + 1
    if isinstance(limit, int):
        return f"lines {first_line}-{first_line + limit - 1}"
    return f"from line {first_line}"
