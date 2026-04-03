from pathlib import Path

from pydantic import BaseModel

from nano_claude_code_py.permissions import (
    NO_PERMISSION_TOOL_NAMES,
    PermissionManager,
    normalize_permission_mode,
    permission_denial_message,
    summarize_tool_request,
)
from nano_claude_code_py.tools.base import ToolContext, ToolResult


class DummyArgs(BaseModel):
    value: str = ""
    file_path: str = ""
    notebook_path: str = ""


class DummyReadTool:
    name = "Read"
    description = "read"
    args_model = DummyArgs
    is_readonly = True

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")


class DummyWriteTool:
    name = "Write"
    description = "write"
    args_model = DummyArgs
    is_readonly = False

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")


class DummyBashTool:
    name = "Bash"
    description = "bash"
    args_model = DummyArgs
    is_readonly = False

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")

    def is_readonly_args(self, args: DummyArgs | None) -> bool:
        return bool(args and args.value == "readonly")


class DummyNotebookEditTool:
    name = "NotebookEdit"
    description = "notebook edit"
    args_model = DummyArgs
    is_readonly = False

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")


class DummyTodoWriteTool:
    name = "TodoWrite"
    description = "todo write"
    args_model = DummyArgs
    is_readonly = False

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")


class DummyGlobTool:
    name = "Glob"
    description = "glob"
    args_model = DummyArgs
    is_readonly = True

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")


class DummyGrepTool:
    name = "Grep"
    description = "grep"
    args_model = DummyArgs
    is_readonly = True

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content="ok")


def test_normalize_permission_mode_supports_legacy_aliases():
    assert normalize_permission_mode("ask") == "default"
    assert normalize_permission_mode("danger-full-access") == "bypassPermissions"
    assert normalize_permission_mode("auto-allow-read") == "dontAsk"


def test_normalize_permission_mode_defaults_unknown_values():
    assert normalize_permission_mode("unknown-mode") == "default"


def test_default_mode_prompts_for_write_and_allows_read():
    manager = PermissionManager(mode="default", prompt=lambda _: True)

    assert manager.allow(DummyReadTool(), "summary") is True
    assert manager.allow(DummyWriteTool(), "summary") is True


def test_accept_edits_allows_write_but_not_bash_without_prompt():
    manager = PermissionManager(mode="acceptEdits")
    cwd = Path("/workspace")

    assert (
        manager.allow(
            DummyWriteTool(),
            "summary",
            args=DummyArgs(file_path="/workspace/out.txt"),
            cwd=cwd,
        )
        is True
    )
    assert (
        manager.allow(
            DummyNotebookEditTool(),
            "summary",
            args=DummyArgs(notebook_path="/workspace/demo.ipynb"),
            cwd=cwd,
        )
        is True
    )
    assert manager.allow(DummyBashTool(), "summary") is False
    assert (
        manager.allow(
            DummyBashTool(),
            "summary",
            args=DummyArgs(value="readonly"),
            cwd=cwd,
        )
        is True
    )


def test_accept_edits_prompts_for_write_outside_working_dir():
    calls: list[str] = []
    manager = PermissionManager(
        mode="acceptEdits",
        prompt=lambda summary: calls.append(summary) or True,
    )

    assert (
        manager.allow(
            DummyWriteTool(),
            "summary",
            args=DummyArgs(file_path="/outside/out.txt"),
            cwd=Path("/workspace"),
        )
        is True
    )
    assert calls == ["summary"]


def test_bypass_permissions_allows_all_tools():
    manager = PermissionManager(mode="bypassPermissions")

    assert manager.allow(DummyWriteTool(), "summary") is True
    assert manager.allow(DummyBashTool(), "summary") is True


def test_plan_and_dont_ask_only_allow_readonly_tools():
    for mode in ("plan", "dontAsk"):
        manager = PermissionManager(mode=mode)
        assert manager.allow(DummyReadTool(), "summary") is True
        assert manager.allow(DummyWriteTool(), "summary") is False
        assert (
            manager.allow(
                DummyBashTool(),
                "summary",
                args=DummyArgs(value="readonly"),
            )
            is True
        )


def test_todo_write_requires_no_permission_checks():
    manager = PermissionManager(mode="default")

    assert "TodoWrite" in NO_PERMISSION_TOOL_NAMES
    assert manager.allow(DummyTodoWriteTool(), "summary") is True


def test_unknown_mode_falls_back_to_default_behavior():
    manager = PermissionManager(mode="custom-mode", prompt=lambda _: True)

    assert manager.allow(DummyReadTool(), "summary") is True
    assert manager.allow(DummyWriteTool(), "summary") is True


def test_summarize_tool_request_uses_source_aligned_short_summaries():
    fallback_summary = (
        'Write [write/exec] {"pattern": '
        '"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}'
    )

    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt"},
        )
        == "Read [read-only] /tmp/demo.txt"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "pages": "2-3"},
        )
        == "Read [read-only] /tmp/demo.txt · pages 2-3"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "offset": 10},
        )
        == "Read [read-only] /tmp/demo.txt · from line 11"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "offset": 10, "limit": 5},
        )
        == "Read [read-only] /tmp/demo.txt · lines 11-15"
    )
    assert (
        summarize_tool_request(
            DummyBashTool(),
            {"command": "printf 'hello world'"},
            args=DummyArgs(value="readonly"),
        )
        == "Bash [read-only] printf 'hello world'"
    )
    assert (
        summarize_tool_request(
            DummyBashTool(),
            {
                "command": "printf 'hello world'",
                "description": "Print a greeting",
            },
        )
        == "Bash [write/exec] Print a greeting"
    )
    assert (
        summarize_tool_request(
            DummyTodoWriteTool(),
            {
                "todos": [
                    {
                        "content": "Run tests",
                        "status": "in_progress",
                        "activeForm": "Running tests",
                    },
                    {
                        "content": "Summarize changes",
                        "status": "pending",
                        "activeForm": "Summarizing changes",
                    },
                ]
            },
        )
        == "TodoWrite [write/exec] 2 items"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "offset": 1},
        )
        == "Read [read-only] /tmp/demo.txt · from line 2"
    )
    assert (
        summarize_tool_request(
            DummyWriteTool(),
            {"pattern": "x" * 80},
        )
        == fallback_summary
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "pages": "1-20"},
        )
        == "Read [read-only] /tmp/demo.txt · pages 1-20"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "offset": 2, "limit": 1},
        )
        == "Read [read-only] /tmp/demo.txt · lines 3-3"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "offset": 2, "limit": None},
        )
        == "Read [read-only] /tmp/demo.txt · from line 3"
    )
    assert (
        summarize_tool_request(
            DummyReadTool(),
            {"file_path": "/tmp/demo.txt", "pages": ""},
        )
        == "Read [read-only] /tmp/demo.txt"
    )
    assert (
        summarize_tool_request(
            DummyWriteTool(),
            {"pattern": "x" * 80},
        )
        == fallback_summary
    )


def test_summarize_tool_request_formats_glob_and_grep_like_source_ui():
    assert (
        summarize_tool_request(
            DummyGlobTool(),
            {"pattern": "*.py", "path": "/tmp/project"},
        )
        == 'Glob [read-only] pattern: "*.py", path: "/tmp/project"'
    )
    assert (
        summarize_tool_request(
            DummyGrepTool(),
            {"pattern": "todo", "path": "/tmp/project"},
        )
        == 'Grep [read-only] pattern: "todo", path: "/tmp/project"'
    )
    assert (
        summarize_tool_request(
            DummyGrepTool(),
            {"pattern": "todo", "path": "."},
        )
        == 'Grep [read-only] pattern: "todo"'
    )


def test_permission_denial_message_matches_mode_specific_source_text():
    dont_ask_message = (
        "Permission to use Write has been denied because Claude Code is "
        "running in don't ask mode. IMPORTANT: You may attempt to "
        "accomplish this action using other tools that might naturally be "
        "used to accomplish this goal, but you should not attempt to work "
        "around this denial in malicious ways. If you believe this "
        "capability is essential to complete the user's request, STOP and "
        "explain to the user what you were trying to do and why you need "
        "this permission. Let the user decide how to proceed."
    )
    default_message = (
        "Permission to use Write has been denied. IMPORTANT: You may attempt "
        "to accomplish this action using other tools that might naturally be "
        "used to accomplish this goal, but you should not attempt to work "
        "around this denial in malicious ways. If you believe this "
        "capability is essential to complete the user's request, STOP and "
        "explain to the user what you were trying to do and why you need "
        "this permission. Let the user decide how to proceed."
    )

    assert (
        permission_denial_message(
            PermissionManager(mode="dontAsk"),
            DummyWriteTool(),
            "Write [write/exec] /tmp/demo.txt",
        )
        == dont_ask_message
    )
    assert (
        permission_denial_message(
            PermissionManager(mode="default", prompt=None),
            DummyWriteTool(),
            "Write [write/exec] /tmp/demo.txt",
        )
        == default_message
    )
