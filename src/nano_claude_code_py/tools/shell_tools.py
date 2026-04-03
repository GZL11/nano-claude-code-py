from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from nano_claude_code_py.tools.base import ToolContext, ToolResult

DEFAULT_TIMEOUT_MS = 120_000
MAX_TIMEOUT_MS = 600_000
SILENT_COMMANDS = {
    "mv",
    "cp",
    "rm",
    "mkdir",
    "rmdir",
    "chmod",
    "chown",
    "chgrp",
    "touch",
    "ln",
    "cd",
    "export",
    "unset",
    "wait",
}
BASH_SEMANTIC_NEUTRAL_COMMANDS = {
    "echo",
    "printf",
    "true",
    "false",
    ":",
}
READ_ONLY_BASH_COMMANDS = {
    "ack",
    "ag",
    "alias",
    "arch",
    "basename",
    "cal",
    "cat",
    "claude",
    "cd",
    "column",
    "comm",
    "cmp",
    "cut",
    "df",
    "dirname",
    "diff",
    "du",
    "echo",
    "expr",
    "expand",
    "false",
    "file",
    "find",
    "fold",
    "fmt",
    "free",
    "getconf",
    "grep",
    "groups",
    "head",
    "hexdump",
    "hostname",
    "history",
    "id",
    "info",
    "ifconfig",
    "ip",
    "jq",
    "less",
    "locate",
    "locale",
    "ls",
    "man",
    "more",
    "nl",
    "nproc",
    "node",
    "numfmt",
    "od",
    "paste",
    "pwd",
    "printf",
    "pr",
    "python",
    "python3",
    "readlink",
    "realpath",
    "rev",
    "rg",
    "seq",
    "sort",
    "stat",
    "strings",
    "sleep",
    "tail",
    "tac",
    "test",
    "time",
    "type",
    "tsort",
    "tree",
    "true",
    "tr",
    "uname",
    "uniq",
    "unexpand",
    "uptime",
    "wc",
    "whereis",
    "which",
    "whoami",
    ":",
    "[",
}
READ_ONLY_DOCKER_SUBCOMMANDS = {
    "images",
    "ps",
}
READ_ONLY_GIT_SUBCOMMANDS = {
    "blame",
    "diff",
    "grep",
    "log",
    "ls-files",
    "rev-parse",
    "show",
    "status",
}
GIT_SHORTLOG_SAFE_FLAGS = {
    "--all": "none",
    "--branches": "none",
    "--tags": "none",
    "--remotes": "none",
    "--since": "string",
    "--after": "string",
    "--until": "string",
    "--before": "string",
    "-s": "none",
    "--summary": "none",
    "-n": "none",
    "--numbered": "none",
    "-e": "none",
    "--email": "none",
    "-c": "none",
    "--committer": "none",
    "--group": "string",
    "--format": "string",
    "--no-merges": "none",
    "--author": "string",
}
GIT_REFLOG_SAFE_FLAGS = {
    "--oneline": "none",
    "--graph": "none",
    "--decorate": "none",
    "--no-decorate": "none",
    "--date": "string",
    "--relative-date": "none",
    "--all": "none",
    "--branches": "none",
    "--tags": "none",
    "--remotes": "none",
    "--since": "string",
    "--after": "string",
    "--until": "string",
    "--before": "string",
    "--max-count": "number",
    "-n": "number",
    "--author": "string",
    "--committer": "string",
    "--grep": "string",
}
GIT_CONFIG_GET_SAFE_FLAGS = {
    "--local": "none",
    "--global": "none",
    "--system": "none",
    "--worktree": "none",
    "--default": "string",
    "--type": "string",
    "--bool": "none",
    "--int": "none",
    "--bool-or-int": "none",
    "--path": "none",
    "--expiry-date": "none",
    "-z": "none",
    "--null": "none",
    "--name-only": "none",
    "--show-origin": "none",
    "--show-scope": "none",
}
GIT_LS_REMOTE_SAFE_FLAGS = {
    "--branches": "none",
    "-b": "none",
    "--tags": "none",
    "-t": "none",
    "--heads": "none",
    "-h": "none",
    "--refs": "none",
    "--quiet": "none",
    "-q": "none",
    "--exit-code": "none",
    "--get-url": "none",
    "--symref": "none",
    "--sort": "string",
}
GIT_REMOTE_SAFE_FLAGS = {
    "-v": "none",
    "--verbose": "none",
}
GIT_REMOTE_SHOW_SAFE_FLAGS = {
    "-n": "none",
}
GIT_TAG_SAFE_FLAGS = {
    "-l": "none",
    "--list": "none",
    "-n": "number",
    "--contains": "string",
    "--no-contains": "string",
    "--merged": "string",
    "--no-merged": "string",
    "--sort": "string",
    "--format": "string",
    "--points-at": "string",
    "--column": "none",
    "--no-column": "none",
    "-i": "none",
    "--ignore-case": "none",
}
GIT_DESCRIBE_SAFE_FLAGS = {
    "--tags": "none",
    "--match": "string",
    "--exclude": "string",
    "--long": "none",
    "--abbrev": "number",
    "--always": "none",
    "--contains": "none",
    "--first-match": "none",
    "--exact-match": "none",
    "--candidates": "number",
    "--dirty": "none",
    "--broken": "none",
}
GIT_REV_LIST_SAFE_FLAGS = {
    "--all": "none",
    "--branches": "none",
    "--tags": "none",
    "--remotes": "none",
    "--since": "string",
    "--after": "string",
    "--until": "string",
    "--before": "string",
    "--max-count": "number",
    "-n": "number",
    "--author": "string",
    "--committer": "string",
    "--grep": "string",
    "--count": "none",
    "--reverse": "none",
    "--first-parent": "none",
    "--ancestry-path": "none",
    "--merges": "none",
    "--no-merges": "none",
    "--min-parents": "number",
    "--max-parents": "number",
    "--no-min-parents": "none",
    "--no-max-parents": "none",
    "--skip": "number",
    "--max-age": "number",
    "--min-age": "number",
    "--walk-reflogs": "none",
    "--oneline": "none",
    "--abbrev-commit": "none",
    "--pretty": "string",
    "--format": "string",
    "--abbrev": "number",
    "--full-history": "none",
    "--dense": "none",
    "--sparse": "none",
    "--source": "none",
    "--graph": "none",
}
GIT_CAT_FILE_SAFE_FLAGS = {
    "-t": "none",
    "-s": "none",
    "-p": "none",
    "-e": "none",
    "--batch-check": "none",
    "--allow-undetermined-type": "none",
}
GIT_FOR_EACH_REF_SAFE_FLAGS = {
    "--format": "string",
    "--sort": "string",
    "--count": "number",
    "--contains": "string",
    "--no-contains": "string",
    "--merged": "string",
    "--no-merged": "string",
    "--points-at": "string",
}
GIT_BRANCH_NONE_SAFE_FLAGS = {
    "-l",
    "--list",
    "-a",
    "--all",
    "-r",
    "--remotes",
    "-v",
    "-vv",
    "--verbose",
    "--color",
    "--no-color",
    "--column",
    "--no-column",
    "--no-abbrev",
    "--merged",
    "--no-merged",
    "--show-current",
    "-i",
    "--ignore-case",
}
GIT_BRANCH_VALUE_SAFE_FLAGS = {
    "--contains": "string",
    "--no-contains": "string",
    "--points-at": "string",
    "--sort": "string",
}
GIT_STASH_LIST_SAFE_FLAGS = {
    "--oneline": "none",
    "--graph": "none",
    "--decorate": "none",
    "--no-decorate": "none",
    "--date": "string",
    "--relative-date": "none",
    "--all": "none",
    "--branches": "none",
    "--tags": "none",
    "--remotes": "none",
    "--max-count": "number",
    "-n": "number",
}
GIT_STASH_SHOW_SAFE_FLAGS = {
    "--stat": "none",
    "--numstat": "none",
    "--shortstat": "none",
    "--name-only": "none",
    "--name-status": "none",
    "--color": "none",
    "--no-color": "none",
    "--patch": "none",
    "-p": "none",
    "--no-patch": "none",
    "--no-ext-diff": "none",
    "-s": "none",
    "--word-diff": "none",
    "--word-diff-regex": "string",
    "--diff-filter": "string",
    "--abbrev": "number",
}
GIT_WORKTREE_LIST_SAFE_FLAGS = {
    "--porcelain": "none",
    "-v": "none",
    "--verbose": "none",
    "--expire": "string",
}
GIT_MERGE_BASE_SAFE_FLAGS = {
    "--is-ancestor": "none",
    "--fork-point": "none",
    "--octopus": "none",
    "--independent": "none",
    "--all": "none",
}
SAFE_WRAPPER_COMMANDS = {
    "env",
    "nice",
    "nohup",
    "stdbuf",
    "time",
    "timeout",
}
GENERIC_SAFE_SEGMENT_RE = r"[^<>()$`|{}&;\n\r]*"
SAFE_ECHO_RE = re.compile(
    r'^echo(?:\s+(?:\'[^\']*\'|"[^"$<>\n\r]*"|[^|;&`$(){}><#\\!"\'\s]+))*'
    r"(?:\s+2>&1)?\s*$"
)
SAFE_FIND_RE = re.compile(
    r"^find(?:\s+(?:\\[()]|(?!-delete\b|-exec\b|-execdir\b|-ok\b|-okdir\b|"
    r"-fprint0?\b|-fls\b|-fprintf\b)[^<>()$`|{}&;\n\r\s]|\s)+)?$"
)
SAFE_CD_RE = re.compile(r'^cd(?:\s+(?:\'[^\']*\'|"[^"]*"|[^\s;|&`$(){}><#\\]+))?$')
SAFE_ARCH_RE = re.compile(r"^arch(?:\s+(?:--help|-h))?\s*$")
SAFE_CLAUDE_HELP_RE = re.compile(r"^claude(?:\s+-h|\s+--help)$")
SAFE_HISTORY_RE = re.compile(r"^history(?:\s+\d+)?\s*$")
SAFE_HOSTNAME_RE = re.compile(r"^hostname(?:\s+(?:-[a-zA-Z]|--[a-zA-Z-]+))*\s*$")
SAFE_IFCONFIG_RE = re.compile(r"^ifconfig(?:\s+[a-zA-Z][a-zA-Z0-9_-]*)?\s*$")
SAFE_IP_ADDR_RE = re.compile(r"^ip addr$")
SAFE_JQ_RE = re.compile(
    r'^jq(?!\s+.*(?:-f\b|--from-file|--rawfile|--slurpfile|--run-tests|'
    r'-L\b|--library-path|\benv\b|\$ENV\b))(?:\s+(?:-[a-zA-Z]+|'
    r'--[a-zA-Z-]+(?:=\S+)?))*(?:\s+\'[^\'`]*\'|\s+"[^"`]*"|'
    r'\s+[^-\s\'"][^\s]*)+\s*$'
)
SAFE_LS_RE = re.compile(rf"^ls(?:\s+{GENERIC_SAFE_SEGMENT_RE})?$")
SAFE_UNIQ_RE = re.compile(
    r"^uniq(?:\s+(?:-[a-zA-Z]+|--[a-zA-Z-]+(?:=\S+)?|-[fsw]\s+\d+))*"
    r"(?:\s|$)\s*$"
)
SAFE_NODE_VERSION_RE = re.compile(r"^node(?:\s+-v|\s+--version)$")
SAFE_PYTHON_VERSION_RE = re.compile(r"^python(?:3)?(?:\s+--version)$")


class RunShellArgs(BaseModel):
    command: str = Field(description="The command to execute")
    timeout: int = Field(
        default=DEFAULT_TIMEOUT_MS,
        ge=1,
        le=MAX_TIMEOUT_MS,
        description=f"Optional timeout in milliseconds (max {MAX_TIMEOUT_MS})",
    )
    description: str | None = Field(
        default=None,
        description=(
            "Clear, concise description of what this command does in active "
            'voice. Never use words like "complex" or "risk" in the '
            "description - just describe what it does."
        ),
    )
    run_in_background: bool | None = Field(
        default=None,
        description=(
            "Set to true to run this command in the background. Use Read to "
            "read the output later."
        ),
    )


class RunShellTool:
    name = "Bash"
    description = "Run shell command"
    args_model = RunShellArgs
    is_readonly = False

    def is_readonly_args(self, args: RunShellArgs | None) -> bool:
        if args is None:
            return False
        return is_readonly_bash_command(args.command)

    def run(self, args: RunShellArgs, ctx: ToolContext) -> ToolResult:
        blocked_reason = blocked_shell_reason(args.command)
        if blocked_reason is not None:
            return ToolResult(content=blocked_reason, is_error=True)
        if not args.run_in_background:
            blocked_sleep = detect_blocked_sleep_pattern(args.command)
            if blocked_sleep is not None:
                return ToolResult(
                    content=(
                        f"Blocked: {blocked_sleep}. Run blocking commands in "
                        "the background with run_in_background: true."
                    ),
                    is_error=True,
                )
        if args.run_in_background:
            return start_background_command(args, ctx)
        try:
            completed = subprocess.run(
                args.command,
                cwd=ctx.cwd,
                shell=True,
                text=True,
                capture_output=True,
                timeout=args.timeout / 1000,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Command timed out after {args.timeout}ms",
                is_error=True,
            )

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        stdout = stdout[:8000]
        stderr = stderr[:8000]
        interpretation = interpret_command_result(
            args.command,
            completed.returncode,
            stdout,
            stderr,
        )
        if not stdout and not stderr:
            if interpretation["message"]:
                return ToolResult(
                    content=interpretation["message"],
                    is_error=interpretation["is_error"],
                )
            if is_silent_bash_command(args.command) and completed.returncode == 0:
                return ToolResult(content="Done")
            if completed.returncode == 0:
                return ToolResult(content="(No output)")
        parts: list[str] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(stderr)
        if interpretation["is_error"] and completed.returncode != 0:
            parts.append(f"Exit code {completed.returncode}")
        return ToolResult(
            content="\n".join(parts).strip() or "(No output)",
            is_error=bool(interpretation["is_error"]),
        )


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


def is_readonly_bash_command(command: str) -> bool:
    if has_output_redirection(command):
        return False
    if contains_unquoted_expansion(command):
        return False

    segments = split_command_for_semantics(command)
    if not segments:
        return False

    for segment in segments:
        raw_segment = segment.strip()
        normalized_segment = normalize_command_segment(raw_segment)
        if not is_readonly_segment(raw_segment, normalized_segment):
            return False
    return True


def is_readonly_segment(raw_command: str, normalized_command: str) -> bool:
    base = extract_base_command(normalized_command)
    if not base:
        return True
    if base == "git":
        return is_readonly_git_command(raw_command, normalized_command)
    if base == "docker":
        return is_readonly_docker_command(normalized_command)
    if base == "echo":
        tokens = normalize_command_tokens(raw_command)
        return bool(SAFE_ECHO_RE.fullmatch(raw_command)) and all(
            "$" not in token for token in tokens[1:]
        )
    if base == "find":
        return bool(SAFE_FIND_RE.fullmatch(normalized_command))
    if base == "cd":
        return bool(SAFE_CD_RE.fullmatch(normalized_command))
    if base == "arch":
        return bool(SAFE_ARCH_RE.fullmatch(normalized_command))
    if base == "claude":
        return bool(SAFE_CLAUDE_HELP_RE.fullmatch(normalized_command))
    if base == "history":
        return bool(SAFE_HISTORY_RE.fullmatch(normalized_command))
    if base == "hostname":
        return bool(SAFE_HOSTNAME_RE.fullmatch(normalized_command))
    if base == "info":
        return info_command_is_safe(normalized_command)
    if base == "ifconfig":
        return bool(SAFE_IFCONFIG_RE.fullmatch(normalized_command))
    if base == "ip":
        return bool(SAFE_IP_ADDR_RE.fullmatch(normalized_command))
    if base == "jq":
        return bool(SAFE_JQ_RE.fullmatch(normalized_command))
    if base == "ls":
        return bool(SAFE_LS_RE.fullmatch(normalized_command))
    if base == "uniq":
        return bool(SAFE_UNIQ_RE.fullmatch(normalized_command))
    if base == "node":
        return bool(SAFE_NODE_VERSION_RE.fullmatch(normalized_command))
    if base in {"python", "python3"}:
        return bool(SAFE_PYTHON_VERSION_RE.fullmatch(normalized_command))
    if base == "alias":
        return normalized_command == "alias"
    if base == "whoami":
        return normalized_command == "whoami"
    if base not in READ_ONLY_BASH_COMMANDS:
        return False
    return matches_safe_simple_command(normalized_command, base)


def has_output_redirection(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return bool(re.search(r"(^|[^<])(?:>>?|>&)", command))

    for token in tokens:
        if token in {">", ">>", ">&"}:
            return True
        if re.match(r"^\d*(?:>>?|>&)\d*$", token):
            return True
        if re.match(r"^\d*(?:>>?|>&).+", token):
            return True
    return False


def is_readonly_git_command(raw_command: str, command: str) -> bool:
    normalized_tokens = normalize_command_tokens(command)
    if len(normalized_tokens) < 2:
        return False
    if normalized_tokens[0] != "git":
        return False

    index = 1
    while index < len(normalized_tokens):
        token = normalized_tokens[index]
        if token == "-c":
            return False
        if token in {"--config-env", "--exec-path"}:
            return False
        if token.startswith("--config-env="):
            return False
        if token.startswith("--exec-path="):
            return False
        if token in {
            "-C",
            "--git-dir",
            "--namespace",
            "--work-tree",
        }:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        break

    if index >= len(normalized_tokens):
        return False

    command_tokens = normalized_tokens[index:]
    if "`" in raw_command:
        return False
    if any("$" in token for token in command_tokens[1:]):
        return False
    if any(
        "{" in token and ("," in token or ".." in token)
        for token in command_tokens[1:]
    ):
        return False

    if len(command_tokens) >= 2 and command_tokens[:2] == ["remote", "show"]:
        return git_remote_show_command_is_safe(command_tokens[2:], raw_command)
    if len(command_tokens) >= 2 and command_tokens[:2] == ["config", "--get"]:
        return git_config_get_command_is_safe(command_tokens[2:], raw_command)
    if len(command_tokens) >= 2 and command_tokens[:2] == ["stash", "list"]:
        return git_stash_list_command_is_safe(command_tokens[2:], raw_command)
    if len(command_tokens) >= 2 and command_tokens[:2] == ["stash", "show"]:
        return git_stash_show_command_is_safe(command_tokens[2:], raw_command)
    if len(command_tokens) >= 2 and command_tokens[:2] == ["worktree", "list"]:
        return git_worktree_list_command_is_safe(command_tokens[2:], raw_command)

    subcommand = command_tokens[0]
    if subcommand == "branch":
        return git_branch_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "cat-file":
        return git_cat_file_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "describe":
        return git_describe_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "for-each-ref":
        return git_for_each_ref_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "ls-remote":
        return git_ls_remote_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "merge-base":
        return git_merge_base_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "remote":
        return git_remote_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "reflog":
        return git_reflog_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "rev-list":
        return git_rev_list_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "shortlog":
        return git_shortlog_command_is_safe(command_tokens[1:], raw_command)
    if subcommand == "tag":
        return git_tag_command_is_safe(command_tokens[1:], raw_command)

    return subcommand in READ_ONLY_GIT_SUBCOMMANDS


def is_readonly_docker_command(command: str) -> bool:
    normalized_tokens = normalize_command_tokens(command)
    if len(normalized_tokens) < 2:
        return False
    if normalized_tokens[0] != "docker":
        return False
    subcommand = normalized_tokens[1]
    if subcommand not in READ_ONLY_DOCKER_SUBCOMMANDS:
        return False
    return matches_safe_simple_command(command, f"docker {subcommand}")


def normalize_command_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.strip().split()

    filtered_tokens = [
        token
        for token in tokens
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", token)
    ]
    index = 0
    while index < len(filtered_tokens):
        token = filtered_tokens[index]
        if token not in SAFE_WRAPPER_COMMANDS:
            break
        skip_count = wrapper_token_span(filtered_tokens[index:])
        if skip_count <= 0:
            break
        index += skip_count
        while index < len(filtered_tokens) and re.match(
            r"^[A-Za-z_][A-Za-z0-9_]*=.*$",
            filtered_tokens[index],
        ):
            index += 1
    return filtered_tokens[index:]


def normalize_command_segment(command: str) -> str:
    normalized_tokens = normalize_command_tokens(command)
    if not normalized_tokens:
        return ""
    return shlex.join(normalized_tokens)


def parse_safe_flag_tokens(
    tokens: list[str],
    safe_flags: dict[str, str],
    *,
    command_name: str | None = None,
    raw_command: str | None = None,
) -> tuple[bool, list[str], set[str]]:
    positionals: list[str] = []
    seen_flags: set[str] = set()
    index = 0
    after_double_dash = False

    if raw_command is not None and "`" in raw_command:
        return False, [], set()

    for token in tokens:
        if "$" in token:
            return False, [], set()
        if "{" in token and ("," in token or ".." in token):
            return False, [], set()

    while index < len(tokens):
        token = tokens[index]
        if after_double_dash:
            positionals.append(token)
            index += 1
            continue
        if token == "--":
            after_double_dash = True
            index += 1
            continue
        if token.startswith("--"):
            flag, separator, value = token.partition("=")
            arg_type = safe_flags.get(flag)
            if arg_type is None:
                return False, [], set()
            seen_flags.add(flag)
            if arg_type == "none":
                if separator:
                    return False, [], set()
                index += 1
                continue
            if separator:
                if not flag_value_is_safe(
                    arg_type,
                    value,
                    flag=flag,
                    command_name=command_name,
                    was_attached=True,
                ):
                    return False, [], set()
                index += 1
                continue
            if index + 1 >= len(tokens):
                return False, [], set()
            if not flag_value_is_safe(
                arg_type,
                tokens[index + 1],
                flag=flag,
                command_name=command_name,
                was_attached=False,
            ):
                return False, [], set()
            index += 2
            continue
        if token.startswith("-") and token != "-":
            if (
                command_name == "git"
                and "-n" in safe_flags
                and re.fullmatch(r"-\d+", token)
            ):
                index += 1
                continue
            arg_type = safe_flags.get(token)
            if arg_type is not None:
                seen_flags.add(token)
                if arg_type == "none":
                    index += 1
                    continue
                if index + 1 >= len(tokens):
                    return False, [], set()
                if not flag_value_is_safe(
                    arg_type,
                    tokens[index + 1],
                    flag=token,
                    command_name=command_name,
                    was_attached=False,
                ):
                    return False, [], set()
                index += 2
                continue

            if "=" not in token and len(token) > 2:
                bundled_flags = [f"-{char}" for char in token[1:]]
                if any(safe_flags.get(flag) != "none" for flag in bundled_flags):
                    return False, [], set()
                seen_flags.update(bundled_flags)
                index += 1
                continue

            return False, [], set()

        positionals.append(token)
        index += 1

    return True, positionals, seen_flags


def flag_value_is_safe(
    arg_type: str,
    value: str,
    *,
    flag: str,
    command_name: str | None,
    was_attached: bool,
) -> bool:
    if arg_type == "number":
        return bool(re.fullmatch(r"-?\d+", value))
    if arg_type == "string" and value.startswith("-"):
        return (
            command_name == "git"
            and flag == "--sort"
            and was_attached
            and bool(re.fullmatch(r"-[a-zA-Z].*", value))
        )
    return bool(value)


def git_shortlog_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_SHORTLOG_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_config_get_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, positionals, _ = parse_safe_flag_tokens(
        tokens,
        GIT_CONFIG_GET_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid and len(positionals) == 1


def git_remote_show_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, positionals, _ = parse_safe_flag_tokens(
        tokens,
        GIT_REMOTE_SHOW_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return (
        is_valid
        and len(positionals) == 1
        and bool(re.fullmatch(r"[a-zA-Z0-9_-]+", positionals[0]))
    )


def git_remote_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, positionals, _ = parse_safe_flag_tokens(
        tokens,
        GIT_REMOTE_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid and not positionals


def git_tag_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, positionals, seen_flags = parse_safe_flag_tokens(
        tokens,
        GIT_TAG_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    if not is_valid:
        return False
    if not positionals:
        return True
    return bool({"-l", "--list"} & seen_flags)


def git_reflog_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, positionals, _ = parse_safe_flag_tokens(
        tokens,
        GIT_REFLOG_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    if not is_valid:
        return False
    if not positionals:
        return True
    return positionals[0] not in {"expire", "delete", "exists"}


def git_ls_remote_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_LS_REMOTE_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_describe_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_DESCRIBE_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_rev_list_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_REV_LIST_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_cat_file_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_CAT_FILE_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_for_each_ref_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_FOR_EACH_REF_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_stash_list_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_STASH_LIST_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_stash_show_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_STASH_SHOW_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_worktree_list_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_WORKTREE_LIST_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_merge_base_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    is_valid, _, _ = parse_safe_flag_tokens(
        tokens,
        GIT_MERGE_BASE_SAFE_FLAGS,
        command_name="git",
        raw_command=raw_command,
    )
    return is_valid


def git_branch_command_is_safe(tokens: list[str], raw_command: str) -> bool:
    if "`" in raw_command:
        return False
    if any("$" in token for token in tokens):
        return False
    if any("{" in token and ("," in token or ".." in token) for token in tokens):
        return False

    index = 0
    seen_list_flag = False
    after_double_dash = False
    last_flag = ""
    optional_value_flags = {"--merged", "--no-merged"}

    while index < len(tokens):
        token = tokens[index]
        if after_double_dash:
            if not seen_list_flag:
                return False
            index += 1
            continue
        if token == "--":
            after_double_dash = True
            last_flag = ""
            index += 1
            continue
        if token.startswith("--"):
            flag, separator, value = token.partition("=")
            if flag in {"--list"}:
                seen_list_flag = True
            if flag == "--abbrev":
                if separator:
                    if not flag_value_is_safe(
                        "number",
                        value,
                        flag=flag,
                        command_name="git",
                        was_attached=True,
                    ):
                        return False
                    last_flag = ""
                else:
                    last_flag = flag
                index += 1
                continue
            if flag in GIT_BRANCH_VALUE_SAFE_FLAGS:
                if separator:
                    if not flag_value_is_safe(
                        GIT_BRANCH_VALUE_SAFE_FLAGS[flag],
                        value,
                        flag=flag,
                        command_name="git",
                        was_attached=True,
                    ):
                        return False
                    last_flag = ""
                    index += 1
                    continue
                if index + 1 >= len(tokens):
                    return False
                if not flag_value_is_safe(
                    GIT_BRANCH_VALUE_SAFE_FLAGS[flag],
                    tokens[index + 1],
                    flag=flag,
                    command_name="git",
                    was_attached=False,
                ):
                    return False
                last_flag = flag
                index += 2
                continue
            if flag in GIT_BRANCH_NONE_SAFE_FLAGS:
                last_flag = flag
                index += 1
                continue
            return False
        if token.startswith("-") and token != "-":
            if token == "-l":
                seen_list_flag = True
                last_flag = token
                index += 1
                continue
            if token in GIT_BRANCH_NONE_SAFE_FLAGS:
                last_flag = token
                index += 1
                continue
            if "=" not in token and len(token) > 2:
                bundled_flags = [f"-{char}" for char in token[1:]]
                if any(
                    flag not in GIT_BRANCH_NONE_SAFE_FLAGS
                    for flag in bundled_flags
                ):
                    return False
                if "-l" in bundled_flags:
                    seen_list_flag = True
                last_flag = token
                index += 1
                continue
            return False

        if not seen_list_flag and last_flag not in optional_value_flags:
            return False
        last_flag = ""
        index += 1

    return True


def matches_safe_simple_command(command: str, base_command: str) -> bool:
    if base_command == "echo":
        return bool(SAFE_ECHO_RE.fullmatch(command))
    if base_command == "find":
        return bool(SAFE_FIND_RE.fullmatch(command))
    if base_command == "history":
        return bool(SAFE_HISTORY_RE.fullmatch(command))
    if base_command == "ifconfig":
        return bool(SAFE_IFCONFIG_RE.fullmatch(command))
    if base_command == "ip":
        return bool(SAFE_IP_ADDR_RE.fullmatch(command))
    if base_command == "jq":
        return bool(SAFE_JQ_RE.fullmatch(command))
    if base_command == "ls":
        return bool(SAFE_LS_RE.fullmatch(command))
    if base_command == "node":
        return bool(SAFE_NODE_VERSION_RE.fullmatch(command))
    if base_command in {"python", "python3"}:
        return bool(SAFE_PYTHON_VERSION_RE.fullmatch(command))
    if base_command == "tree":
        return tree_command_is_safe(command)
    if base_command == "uniq":
        return bool(SAFE_UNIQ_RE.fullmatch(command))
    if base_command in {"alias", "pwd", "whoami"}:
        return command == base_command
    pattern = re.compile(
        rf"^{re.escape(base_command)}(?:\s|$)[^<>()$`|{{}}&;\n\r]*$"
    )
    return bool(pattern.fullmatch(command))


def tree_command_is_safe(command: str) -> bool:
    tokens = normalize_command_tokens(command)
    if not tokens or tokens[0] != "tree":
        return False
    for token in tokens[1:]:
        if token == "-R":
            return False
        if token in {"-o", "--output"}:
            return False
        if token.startswith("--output="):
            return False
        if token.startswith("-o") and token != "-o":
            return False
    return matches_safe_simple_command_fallback(command, "tree")


def info_command_is_safe(command: str) -> bool:
    tokens = normalize_command_tokens(command)
    if not tokens or tokens[0] != "info":
        return False

    blocked_flags = {
        "-o",
        "--output",
        "--dribble",
        "--init-file",
        "--restore",
    }
    for token in tokens[1:]:
        if token in blocked_flags:
            return False
        if any(
            token.startswith(f"{flag}=")
            for flag in blocked_flags
            if flag.startswith("--")
        ):
            return False
    return matches_safe_simple_command_fallback(command, "info")


def matches_safe_simple_command_fallback(
    command: str,
    base_command: str,
) -> bool:
    pattern = re.compile(
        rf"^{re.escape(base_command)}(?:\s|$)[^<>()$`|{{}}&;\n\r]*$"
    )
    return bool(pattern.fullmatch(command))


def contains_unquoted_expansion(command: str) -> bool:
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for index, char in enumerate(command):
        if escaped:
            escaped = False
            continue

        if char == "\\" and not in_single_quote:
            escaped = True
            continue

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue

        if in_single_quote:
            continue

        if char == "$":
            next_char = command[index + 1] if index + 1 < len(command) else ""
            if next_char and re.fullmatch(r"[A-Za-z_@*#?!$0-9-]", next_char):
                return True

        if in_double_quote:
            continue

        if char in {"?", "*", "[", "]"}:
            return True

    return False


def wrapper_token_span(tokens: list[str]) -> int:
    first = tokens[0]
    if first == "nohup":
        return 1
    if first == "time":
        span = 1
        while span < len(tokens) and tokens[span].startswith("-"):
            span += 1
        return span
    if first == "nice":
        if len(tokens) > 2 and tokens[1] in {"-n", "--adjustment"}:
            return 3
        if len(tokens) > 1 and re.fullmatch(r"-?\d+", tokens[1]):
            return 2
        return 1
    if first == "timeout":
        span = 1
        while span < len(tokens):
            token = tokens[span]
            if token in {"-k", "--kill-after", "-s", "--signal"}:
                if span + 1 >= len(tokens):
                    return span + 1
                span += 2
                continue
            if token.startswith("-"):
                span += 1
                continue
            span += 1
            break
        return span
    if first == "stdbuf":
        span = 1
        while span < len(tokens):
            token = tokens[span]
            if token in {"-i", "-o", "-e"}:
                if span + 1 >= len(tokens):
                    return span + 1
                span += 2
                continue
            if re.fullmatch(r"-(?:i|o|e).+", token):
                span += 1
                continue
            break
        return span
    if first == "env":
        span = 1
        while span < len(tokens):
            token = tokens[span]
            if token in {"-i", "--ignore-environment", "--"}:
                span += 1
                continue
            if token in {"-u", "--unset"}:
                if span + 1 >= len(tokens):
                    return span + 1
                span += 2
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", token):
                span += 1
                continue
            break
        return span
    return 0


def detect_blocked_sleep_pattern(command: str) -> str | None:
    parts = split_command_tokens(
        command,
        operators=("&&", "||", ";"),
        include_operators=False,
        maxsplit=1,
    )
    first = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    match = re.fullmatch(r"sleep\s+(\d+)\s*", first.strip())
    if match is None:
        return None
    seconds = int(match.group(1))
    if seconds < 2:
        return None
    remainder = rest.strip()
    if remainder:
        return f"sleep {seconds} followed by: {remainder}"
    return f"standalone sleep {seconds}"


def is_silent_bash_command(command: str) -> bool:
    parts = split_command_with_operators(command)
    if not parts:
        return False
    has_command = False
    last_operator: str | None = None
    skip_next_as_redirect_target = False
    for part in parts:
        if skip_next_as_redirect_target:
            skip_next_as_redirect_target = False
            continue
        if part in {">", ">>", ">&"}:
            skip_next_as_redirect_target = True
            continue
        if part in {"||", "&&", "|", ";"}:
            last_operator = part
            continue
        base_command = extract_base_command(part)
        if not base_command:
            continue
        if (
            last_operator == "||"
            and base_command in BASH_SEMANTIC_NEUTRAL_COMMANDS
        ):
            continue
        has_command = True
        if base_command not in SILENT_COMMANDS:
            return False
    return has_command


def interpret_command_result(
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> dict[str, str | bool | None]:
    _ = stdout, stderr
    base_command = extract_base_command(last_command_segment(command))
    if base_command in {"grep", "rg"}:
        return {
            "is_error": exit_code >= 2,
            "message": "No matches found" if exit_code == 1 else None,
        }
    if base_command == "find":
        return {
            "is_error": exit_code >= 2,
            "message": (
                "Some directories were inaccessible"
                if exit_code == 1
                else None
            ),
        }
    if base_command == "diff":
        return {
            "is_error": exit_code >= 2,
            "message": "Files differ" if exit_code == 1 else None,
        }
    if base_command in {"test", "["}:
        return {
            "is_error": exit_code >= 2,
            "message": "Condition is false" if exit_code == 1 else None,
        }
    return {
        "is_error": exit_code != 0,
        "message": (
            f"Command failed with exit code {exit_code}"
            if exit_code != 0
            else None
        ),
    }


def split_command_for_semantics(command: str) -> list[str]:
    return split_command_tokens(
        command,
        operators=("&&", "||", "|", ";"),
        include_operators=False,
    )


def split_command_with_operators(command: str) -> list[str]:
    return split_command_tokens(
        command,
        operators=("&&", "||", "|", ";", ">>", ">&", ">"),
        include_operators=True,
    )


def split_command_tokens(
    command: str,
    *,
    operators: tuple[str, ...],
    include_operators: bool,
    maxsplit: int | None = None,
) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    splits = 0
    index = 0
    ordered_operators = tuple(sorted(operators, key=len, reverse=True))

    while index < len(command):
        if quote is not None:
            char = command[index]
            current.append(char)
            if char == "\\" and quote == '"' and index + 1 < len(command):
                index += 1
                current.append(command[index])
            elif char == quote:
                quote = None
            index += 1
            continue

        char = command[index]
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            index += 1
            continue
        if char == "\\" and index + 1 < len(command):
            current.append(char)
            index += 1
            current.append(command[index])
            index += 1
            continue
        matched_operator = next(
            (
                operator
                for operator in ordered_operators
                if command.startswith(operator, index)
            ),
            None,
        )
        if (
            matched_operator is not None
            and (maxsplit is None or splits < maxsplit)
        ):
            segment = "".join(current).strip()
            if segment:
                parts.append(segment)
            if include_operators:
                parts.append(matched_operator)
            current = []
            index += len(matched_operator)
            splits += 1
            continue

        current.append(char)
        index += 1

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def last_command_segment(command: str) -> str:
    parts = split_command_for_semantics(command)
    return parts[-1] if parts else command


def extract_base_command(command: str) -> str:
    if not command.strip():
        return ""
    normalized_tokens = normalize_command_tokens(command)
    return normalized_tokens[0] if normalized_tokens else ""


def start_background_command(args: RunShellArgs, ctx: ToolContext) -> ToolResult:
    task_id = f"bash-{uuid.uuid4().hex[:12]}"
    output_path = background_output_path(task_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle = output_path.open("w", encoding="utf-8")
    try:
        subprocess.Popen(
            args.command,
            cwd=ctx.cwd,
            shell=True,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        handle.close()
        raise
    handle.close()
    return ToolResult(
        content=(
            f"Command running in background with ID: {task_id}. "
            f"Output is being written to: {output_path}"
        )
    )


def background_output_path(task_id: str) -> Path:
    return Path(tempfile.gettempdir()) / "nano-claude-code-py" / f"{task_id}.log"
