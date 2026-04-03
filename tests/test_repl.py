import io

from rich.console import Console

import nano_claude_code_py.repl as repl_module
from nano_claude_code_py.config import Settings
from nano_claude_code_py.repl import (
    DEFAULT_HISTORY_LIMIT,
    format_permission_prompt,
    handle_local_command,
    parse_export_path,
    parse_history_limit,
    render_history,
    render_session_summary,
)
from nano_claude_code_py.session import SessionTranscript, default_export_path
from nano_claude_code_py.tools.registry import default_registry


def test_parse_history_limit_defaults_and_clamps():
    assert parse_history_limit("/history") == DEFAULT_HISTORY_LIMIT
    assert parse_history_limit("/history nope") == DEFAULT_HISTORY_LIMIT
    assert parse_history_limit("/history 0") == 1
    assert parse_history_limit("/history 999") == 100


def test_render_history_outputs_recent_messages():
    transcript = SessionTranscript()
    transcript.add("user", "first")
    transcript.add("assistant", "second")
    transcript.add("user", "third")

    output = render_history(transcript, 2)

    assert "2. assistant: second" in output
    assert "3. user: third" in output
    assert "1. user: first" not in output


def test_render_session_summary_includes_path_and_count(tmp_path):
    transcript = SessionTranscript()
    transcript.add("user", "hello")
    session_path = tmp_path / "20240102-000000.jsonl"

    output = render_session_summary(transcript, session_path, tmp_path)

    assert str(session_path) in output
    assert "message_count: 1" in output
    assert f"workspace: {tmp_path}" in output


def test_parse_export_path_defaults_to_txt_sibling(tmp_path):
    session_path = tmp_path / "20240102-000000.jsonl"

    assert parse_export_path(
        "/export",
        session_path,
    ) == default_export_path(session_path)
    assert parse_export_path(
        "/export custom.txt",
        session_path,
    ) == tmp_path / "custom.txt"


def test_clear_command_persists_empty_transcript(tmp_path):
    transcript = SessionTranscript()
    transcript.add("user", "hello")
    session_path = tmp_path / "20240102-000000.jsonl"
    transcript.save_jsonl(session_path)

    handled = handle_local_command(
        "/clear",
        transcript=transcript,
        settings=Settings(session_dir=tmp_path, cwd=tmp_path),
        session_path=session_path,
        cwd=tmp_path,
        registry=default_registry(),
    )

    assert handled is True
    assert not transcript.messages
    assert SessionTranscript.load_jsonl(session_path).messages == []


def test_save_command_persists_transcript(tmp_path):
    transcript = SessionTranscript()
    transcript.add("user", "hello")
    session_path = tmp_path / "20240102-000000.jsonl"

    handled = handle_local_command(
        "/save",
        transcript=transcript,
        settings=Settings(session_dir=tmp_path, cwd=tmp_path),
        session_path=session_path,
        cwd=tmp_path,
        registry=default_registry(),
    )

    assert handled is True
    saved = SessionTranscript.load_jsonl(session_path)
    assert len(saved.messages) == 1
    assert saved.messages[0].text_content() == "hello"


def test_help_command_lists_export(tmp_path):
    transcript = SessionTranscript()
    session_path = tmp_path / "20240102-000000.jsonl"
    output = io.StringIO()
    original_console = repl_module.console
    repl_module.console = Console(file=output, force_terminal=False)
    try:
        handled = handle_local_command(
            "/help",
            transcript=transcript,
            settings=Settings(session_dir=tmp_path, cwd=tmp_path),
            session_path=session_path,
            cwd=tmp_path,
            registry=default_registry(),
        )
    finally:
        repl_module.console = original_console

    assert handled is True
    rendered = output.getvalue().replace("\n", " ")
    assert "/help" in rendered
    assert "/export [path]" in rendered
    assert "/exit" in rendered


def test_format_permission_prompt_keeps_literal_confirmation_suffix():
    assert (
        format_permission_prompt("Bash [write/exec] git push")
        == "Permission: Bash [write/exec] git push [y/N] "
    )
