import time

from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.shell_tools import (
    RunShellArgs,
    RunShellTool,
    background_output_path,
    blocked_shell_reason,
    detect_blocked_sleep_pattern,
    is_readonly_bash_command,
)


def test_run_shell_success(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(RunShellArgs(command="printf 'ok'"), ctx)

    assert not result.is_error
    assert result.content == "ok"


def test_run_shell_blocks_dangerous_commands(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(RunShellArgs(command="rm -rf /"), ctx)

    assert result.is_error
    assert "Blocked dangerous command" in result.content


def test_blocked_shell_reason_detects_shutdown_patterns():
    assert blocked_shell_reason("shutdown now") is not None
    assert blocked_shell_reason("echo ok") is None


def test_run_shell_honors_timeout_in_milliseconds(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(
        RunShellArgs(command="sleep 0.1", timeout=10),
        ctx,
    )

    assert result.is_error
    assert "Command timed out after 10ms" in result.content


def test_run_shell_accepts_optional_description_field(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(
        RunShellArgs(
            command="printf 'ok'",
            description="Print a short success marker",
        ),
        ctx,
    )

    assert not result.is_error
    assert "ok" in result.content


def test_run_shell_can_start_background_command(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    result = RunShellTool().run(
        RunShellArgs(
            command="printf 'ok from background'",
            run_in_background=True,
        ),
        ctx,
    )

    assert not result.is_error
    assert "Command running in background with ID:" in result.content
    task_id = result.content.split("ID: ", maxsplit=1)[1].split(".", maxsplit=1)[0]
    output_path = background_output_path(task_id)

    for _ in range(20):
        if output_path.exists() and "ok from background" in output_path.read_text(
            encoding="utf-8"
        ):
            break
        time.sleep(0.05)

    assert output_path.exists()
    assert "ok from background" in output_path.read_text(encoding="utf-8")


def test_run_shell_blocks_long_sleep_without_background(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = RunShellTool().run(RunShellArgs(command="sleep 2"), ctx)

    assert result.is_error
    assert "standalone sleep 2" in result.content
    assert "run_in_background: true" in result.content


def test_detect_blocked_sleep_pattern_ignores_pipelines():
    assert detect_blocked_sleep_pattern("sleep 2 | cat") is None
    assert (
        detect_blocked_sleep_pattern("sleep 2 && echo ok")
        == "sleep 2 followed by: echo ok"
    )


def test_run_shell_treats_no_match_grep_as_non_error(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = RunShellTool().run(
        RunShellArgs(command="printf 'alpha\\n' | grep beta"),
        ctx,
    )

    assert not result.is_error
    assert result.content == "No matches found"


def test_run_shell_reports_done_for_silent_success(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = RunShellTool().run(RunShellArgs(command="mkdir demo-dir"), ctx)

    assert not result.is_error
    assert result.content == "Done"


def test_run_shell_reports_exit_code_without_legacy_prefixes_on_error(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = RunShellTool().run(RunShellArgs(command="sh -c 'exit 7'"), ctx)

    assert result.is_error
    assert result.content == "Command failed with exit code 7"


def test_is_readonly_bash_command_is_conservative():
    assert is_readonly_bash_command("pwd") is True
    assert is_readonly_bash_command("git status") is True
    assert is_readonly_bash_command("git reflog") is True
    assert is_readonly_bash_command("git reflog show HEAD") is True
    assert is_readonly_bash_command("git cat-file -t HEAD") is True
    assert is_readonly_bash_command("git for-each-ref --format=%(refname)") is True
    assert is_readonly_bash_command("git ls-remote --tags origin") is True
    assert is_readonly_bash_command("git describe --tags HEAD") is True
    assert is_readonly_bash_command("git rev-list --count HEAD") is True
    assert is_readonly_bash_command("git stash list --max-count 5") is True
    assert is_readonly_bash_command("git stash show -p stash@{0}") is True
    assert is_readonly_bash_command("git shortlog -sn") is True
    assert is_readonly_bash_command("git worktree list --porcelain") is True
    assert is_readonly_bash_command("git merge-base --all HEAD main") is True
    assert is_readonly_bash_command("git remote -v") is True
    assert is_readonly_bash_command("git remote show -n origin") is True
    assert is_readonly_bash_command("git tag") is True
    assert is_readonly_bash_command("git tag -li pattern") is True
    assert is_readonly_bash_command("git branch --list") is True
    assert is_readonly_bash_command("git branch --merged main") is True
    assert is_readonly_bash_command("git rev-list -5 HEAD") is True
    assert is_readonly_bash_command("git tag --sort=-refname") is True
    assert is_readonly_bash_command("git for-each-ref --sort=-refname") is True
    assert is_readonly_bash_command("git config --get user.name") is True
    assert is_readonly_bash_command("git stash show stash@{0}") is True
    assert is_readonly_bash_command("FOO=bar timeout 10 git status") is True
    assert is_readonly_bash_command("docker ps") is True
    assert is_readonly_bash_command("env -i pwd") is True
    assert is_readonly_bash_command("arch --help") is True
    assert is_readonly_bash_command("claude --help") is True
    assert is_readonly_bash_command("cd /tmp && pwd") is True
    assert is_readonly_bash_command("echo 'a|b'") is True
    assert is_readonly_bash_command("expr 1 + 1") is True
    assert is_readonly_bash_command("fmt notes.txt") is True
    assert is_readonly_bash_command("history 10") is True
    assert is_readonly_bash_command("hostname -f") is True
    assert is_readonly_bash_command("info bash") is True
    assert is_readonly_bash_command("alias") is True
    assert is_readonly_bash_command("type ls") is True
    assert is_readonly_bash_command("whoami") is True
    assert is_readonly_bash_command("node -v") is True
    assert is_readonly_bash_command("python3 --version") is True
    assert is_readonly_bash_command("ip addr") is True
    assert is_readonly_bash_command("ifconfig eth0") is True
    assert is_readonly_bash_command("echo $HOME") is False
    assert is_readonly_bash_command('cd "$HOME"') is False
    assert is_readonly_bash_command("ls *") is False
    assert is_readonly_bash_command('jq "." $FILE') is False
    assert is_readonly_bash_command("find ./ -?xec") is False
    assert is_readonly_bash_command("find . -exec rm {} \\;") is False
    assert is_readonly_bash_command("git -c core.fsmonitor=true status") is False
    assert is_readonly_bash_command("git --exec-path=/tmp status") is False
    assert is_readonly_bash_command(
        "git --config-env=core.fsmonitor=EVIL status"
    ) is False
    assert is_readonly_bash_command("git cat-file --batch HEAD") is False
    assert is_readonly_bash_command("git for-each-ref --shell") is False
    assert is_readonly_bash_command("git reflog expire --all") is False
    assert is_readonly_bash_command("git ls-remote --server-option=foo origin") is False
    assert is_readonly_bash_command("git describe --match -foo") is False
    assert is_readonly_bash_command("git for-each-ref --sort -refname") is False
    assert is_readonly_bash_command("git status `echo foo`") is False
    assert is_readonly_bash_command("git for-each-ref {foo,bar}") is False
    assert is_readonly_bash_command("git rev-list {1..3}") is False
    assert is_readonly_bash_command("git remote origin") is False
    assert is_readonly_bash_command("git remote show origin extra") is False
    assert is_readonly_bash_command("git tag foo") is False
    assert is_readonly_bash_command("git branch foo") is False
    assert is_readonly_bash_command("git branch --abbrev 10") is False
    assert is_readonly_bash_command("git config user.name") is False
    assert is_readonly_bash_command("hostname new-name") is False
    assert is_readonly_bash_command("info --output out.txt bash") is False
    assert is_readonly_bash_command("jq -f filter.jq data.json") is False
    assert is_readonly_bash_command("tree -o out.txt") is False
    assert is_readonly_bash_command("tree -R -H . -L 2") is False
    assert is_readonly_bash_command("node -v --run test") is False
    assert is_readonly_bash_command("claude --help extra") is False
    assert is_readonly_bash_command("uniq file.txt") is False
    assert is_readonly_bash_command("python3 -c 'print(1)'") is False
    assert is_readonly_bash_command("printf 'x' > out.txt") is False
    assert is_readonly_bash_command("mkdir demo-dir") is False
