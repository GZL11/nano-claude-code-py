from __future__ import annotations

import re
import subprocess

from pydantic import BaseModel, Field

from nano_claude_code_py.tools.base import ToolContext, ToolResult


class RunShellArgs(BaseModel):
    command: str
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class RunShellTool:
    name = "run_shell"
    description = "Run a shell command and capture stdout, stderr, and exit code."
    args_model = RunShellArgs
    is_readonly = False

    def run(self, args: RunShellArgs, ctx: ToolContext) -> ToolResult:
        blocked_reason = blocked_shell_reason(args.command)
        if blocked_reason is not None:
            return ToolResult(content=blocked_reason, is_error=True)
        try:
            completed = subprocess.run(
                args.command,
                cwd=ctx.cwd,
                shell=True,
                text=True,
                capture_output=True,
                timeout=args.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Command timed out after {args.timeout_seconds}s",
                is_error=True,
            )

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        stdout = stdout[:8000]
        stderr = stderr[:8000]
        output = "\n".join(
            [
                f"exit_code: {completed.returncode}",
                f"stdout:\n{stdout}",
                f"stderr:\n{stderr}",
            ]
        ).strip()
        return ToolResult(content=output, is_error=completed.returncode != 0)


BLOCKED_SHELL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(^|[;&|]\s*)rm\s+-rf\s+/(?:\s|$)"),
        "Blocked dangerous command: rm -rf /",
    ),
    (
        re.compile(r"(^|[;&|]\s*)sudo\s+rm\s+-rf\s+/(?:\s|$)"),
        "Blocked dangerous command: sudo rm -rf /",
    ),
    (
        re.compile(r"(^|[;&|]\s*)(shutdown|reboot|halt|poweroff)(?:\s|$)"),
        "Blocked dangerous command: system shutdown/reboot",
    ),
    (
        re.compile(r"(^|[;&|]\s*)mkfs(?:\.[a-z0-9]+)?(?:\s|$)", re.IGNORECASE),
        "Blocked dangerous command: mkfs",
    ),
    (
        re.compile(r"(^|[;&|]\s*)dd\s+.*of=/dev/", re.IGNORECASE),
        "Blocked dangerous command: dd to /dev/*",
    ),
]


def blocked_shell_reason(command: str) -> str | None:
    normalized = " ".join(command.strip().split())
    for pattern, reason in BLOCKED_SHELL_PATTERNS:
        if pattern.search(normalized):
            return reason
    return None
