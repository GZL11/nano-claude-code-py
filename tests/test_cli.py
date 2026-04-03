from typer.testing import CliRunner

from nano_claude_code_py import cli
from nano_claude_code_py.cli import app
from nano_claude_code_py.session import SessionTranscript, default_export_path

runner = CliRunner()


def test_root_command_defaults_to_chat(monkeypatch):
    called: list[tuple[str, object]] = []

    monkeypatch.setattr(
        cli,
        "chat",
        lambda **kwargs: called.append(("chat", kwargs)),
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert called == [
        (
            "chat",
            {"model": None, "permission_mode": None, "session_dir": None},
        )
    ]


def test_root_command_supports_print_alias(monkeypatch):
    called: list[tuple[str, object]] = []

    monkeypatch.setattr(
        cli,
        "run",
        lambda prompt, **kwargs: called.append(("run", prompt, kwargs)),
    )

    result = runner.invoke(app, ["-p", "hello"])

    assert result.exit_code == 0
    assert called == [
        (
            "run",
            "hello",
            {"model": None, "permission_mode": None, "session_dir": None},
        )
    ]


def test_root_command_supports_resume_alias(monkeypatch):
    called: list[tuple[str, object]] = []

    monkeypatch.setattr(
        cli,
        "resume",
        lambda **kwargs: called.append(("resume", kwargs)),
    )

    result = runner.invoke(app, ["--continue"])

    assert result.exit_code == 0
    assert called == [
        ("resume", {"model": None, "permission_mode": None, "session_dir": None})
    ]


def test_sessions_command_lists_saved_sessions(tmp_path):
    transcript = SessionTranscript()
    transcript.add("user", "hello world")
    transcript.save_jsonl(tmp_path / "20240102-000000.jsonl")

    result = runner.invoke(app, ["sessions", "--session-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Saved Sessions" in result.stdout
    assert "20240102-000000.jsonl" in result.stdout


def test_resume_fails_when_no_saved_transcript(tmp_path):
    result = runner.invoke(app, ["resume", "--session-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "No saved transcript found." in result.stdout


def test_export_command_writes_default_plaintext_file(tmp_path):
    transcript = SessionTranscript()
    transcript.add("user", "hello world")
    session_path = tmp_path / "20240102-000000.jsonl"
    transcript.save_jsonl(session_path)

    result = runner.invoke(app, ["export", "--session-dir", str(tmp_path)])

    assert result.exit_code == 0
    export_path = default_export_path(session_path)
    assert export_path.exists()
    assert "## 1. user" in export_path.read_text(encoding="utf-8")
    assert str(export_path) in result.stdout


def test_export_command_respects_custom_output_path(tmp_path):
    transcript = SessionTranscript()
    transcript.add("user", "hello world")
    transcript.save_jsonl(tmp_path / "20240102-000000.jsonl")

    result = runner.invoke(
        app,
        [
            "export",
            "--session-dir",
            str(tmp_path),
            "--output",
            "exports/chat.txt",
        ],
    )

    assert result.exit_code == 0
    export_path = tmp_path / "exports" / "chat.txt"
    assert export_path.exists()
    assert "hello world" in export_path.read_text(encoding="utf-8")
