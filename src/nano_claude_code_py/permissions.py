from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nano_claude_code_py.tools.base import Tool


PermissionMode = str
PromptFn = Callable[[str], bool]


@dataclass
class PermissionManager:
    mode: PermissionMode = "ask"
    prompt: PromptFn | None = None

    def allow(self, tool: Tool, summary: str) -> bool:
        if self.mode == "danger-full-access":
            return True
        if self.mode == "auto-allow-read":
            return tool.is_readonly
        if self.mode != "ask":
            return False
        if tool.is_readonly:
            return True
        if self.prompt is None:
            return False
        return self.prompt(summary)


def summarize_tool_request(tool: Tool, arguments: dict[str, object]) -> str:
    access = "read-only" if tool.is_readonly else "write/exec"
    serialized = json.dumps(arguments, ensure_ascii=True, sort_keys=True)
    if len(serialized) > 180:
        serialized = serialized[:177] + "..."
    return f"{tool.name} [{access}] {serialized}"
