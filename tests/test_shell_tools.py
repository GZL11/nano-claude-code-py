from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.shell_tools import (
    RunShellArgs,
    RunShellTool,
    blocked_shell_reason,
)


def test_run_shell_success(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(RunShellArgs(command="printf 'ok'"), ctx)

    assert not result.is_error
    assert "exit_code: 0" in result.content
    assert "ok" in result.content


def test_run_shell_blocks_dangerous_commands(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(RunShellArgs(command="rm -rf /"), ctx)

    assert result.is_error
    assert "Blocked dangerous command" in result.content


def test_blocked_shell_reason_detects_shutdown_patterns():
    assert blocked_shell_reason("shutdown now") is not None
    assert blocked_shell_reason("echo ok") is None
