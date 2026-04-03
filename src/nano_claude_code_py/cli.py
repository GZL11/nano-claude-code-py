from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from nano_claude_code_py import __version__
from nano_claude_code_py.config import Settings
from nano_claude_code_py.llm.client import AnthropicModelClient
from nano_claude_code_py.llm.tool_loop import run_turn
from nano_claude_code_py.permissions import PermissionManager
from nano_claude_code_py.prompts import build_system_prompt
from nano_claude_code_py.repl import format_permission_prompt, run_repl
from nano_claude_code_py.session import (
    SessionTranscript,
    default_export_path,
    default_session_path,
    list_sessions,
    load_latest_session,
    load_selected_session,
)
from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.registry import default_registry

app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main_callback(
    ctx: typer.Context,
    prompt: str | None = typer.Option(
        None,
        "--print",
        "-p",
        help="Run a single prompt and print the response.",
    ),
    resume_latest: bool = typer.Option(
        False,
        "--resume",
        help="Resume the latest saved transcript.",
    ),
    continue_latest: bool = typer.Option(
        False,
        "--continue",
        help="Alias for --resume.",
    ),
    model: str | None = typer.Option(default=None),
    language: str | None = typer.Option(default=None),
    permission_mode: str | None = typer.Option(default=None),
    session_dir: str | None = typer.Option(default=None),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    if prompt is not None:
        run(
            prompt,
            model=model,
            language=language,
            permission_mode=permission_mode,
            session_dir=session_dir,
        )
        return

    if resume_latest or continue_latest:
        resume(
            model=model,
            language=language,
            permission_mode=permission_mode,
            session_dir=session_dir,
        )
        return

    chat(
        model=model,
        language=language,
        permission_mode=permission_mode,
        session_dir=session_dir,
    )


@app.command()
def chat(
    model: str | None = typer.Option(default=None),
    language: str | None = typer.Option(default=None),
    permission_mode: str | None = typer.Option(default=None),
    resume: bool = typer.Option(default=False, help="Resume the latest transcript."),
    session_dir: str | None = typer.Option(default=None),
) -> None:
    """Start the interactive REPL."""
    settings = Settings()
    if model is not None:
        settings.model = model
    if language is not None:
        settings.language = language
    if permission_mode is not None:
        settings.permission_mode = permission_mode
    if session_dir is not None:
        settings.session_dir = settings.session_dir.__class__(session_dir)
    transcript = None
    session_path = None
    if resume:
        transcript, session_path = load_latest_session(settings.session_dir)
        if session_path is None:
            console.print("No saved transcript found. Starting a new session.")
    run_repl(settings, transcript=transcript, session_path=session_path)


@app.command()
def run(
    prompt: str,
    model: str | None = typer.Option(default=None),
    language: str | None = typer.Option(default=None),
    permission_mode: str | None = typer.Option(default=None),
    session_dir: str | None = typer.Option(default=None),
) -> None:
    """Run a single prompt."""
    settings = Settings()
    if model is not None:
        settings.model = model
    if language is not None:
        settings.language = language
    if permission_mode is not None:
        settings.permission_mode = permission_mode
    if session_dir is not None:
        settings.session_dir = settings.session_dir.__class__(session_dir)
    if not settings.anthropic_api_key:
        raise typer.BadParameter("ANTHROPIC_API_KEY is required for run mode")

    transcript = SessionTranscript()
    transcript.add("user", prompt)

    permission_manager = PermissionManager(
        mode=settings.permission_mode,
        prompt=lambda summary: console.input(
            format_permission_prompt(summary)
        ).strip().lower()
        in {"y", "yes"},
    )
    response = run_turn(
        AnthropicModelClient(
            api_key=settings.anthropic_api_key,
            model=settings.model,
        ),
        default_registry(),
        transcript.messages,
        system_prompt=build_system_prompt(settings.language),
        tool_context=ToolContext(cwd=settings.cwd),
        permission_manager=permission_manager,
        console=console,
        on_text=lambda text: console.print(text, end=""),
        stream=True,
    )
    if response.text and not response.was_streamed:
        console.print(response.text)
    transcript.save_jsonl(default_session_path(settings.session_dir))


@app.command()
def resume(
    model: str | None = typer.Option(default=None),
    language: str | None = typer.Option(default=None),
    permission_mode: str | None = typer.Option(default=None),
    session: str | None = typer.Option(
        default=None,
        help="Resume a specific session file or stem.",
    ),
    index: int | None = typer.Option(
        default=None,
        help="Resume a session by 1-based index from `sessions`.",
    ),
    session_dir: str | None = typer.Option(default=None),
) -> None:
    """Resume a saved transcript in chat mode."""
    settings = Settings()
    if model is not None:
        settings.model = model
    if language is not None:
        settings.language = language
    if permission_mode is not None:
        settings.permission_mode = permission_mode
    if session_dir is not None:
        settings.session_dir = settings.session_dir.__class__(session_dir)
    transcript, session_path = load_selected_session(
        settings.session_dir,
        name=session,
        index=index,
    )
    if session_path is None:
        console.print("No saved transcript found.")
        raise typer.Exit(code=1)
    run_repl(settings, transcript=transcript, session_path=session_path)


@app.command(name="sessions")
def sessions_cmd(
    session_dir: str | None = typer.Option(default=None),
) -> None:
    """List saved local transcripts."""
    settings = Settings()
    if session_dir is not None:
        settings.session_dir = settings.session_dir.__class__(session_dir)
    sessions = list_sessions(settings.session_dir)
    if not sessions:
        console.print("No saved sessions.")
        raise typer.Exit(code=0)

    table = Table(title="Saved Sessions")
    table.add_column("#", justify="right")
    table.add_column("File")
    table.add_column("Messages", justify="right")
    table.add_column("Updated")
    table.add_column("Preview")
    for idx, session in enumerate(sessions, start=1):
        table.add_row(
            str(idx),
            session.path.name,
            str(session.message_count),
            session.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            session.preview or "-",
        )
    console.print(table)


@app.command()
def export(
    session: str | None = typer.Option(
        default=None,
        help="Export a specific session file or stem.",
    ),
    index: int | None = typer.Option(
        default=None,
        help="Export a session by 1-based index from `sessions`.",
    ),
    output: str | None = typer.Option(
        default=None,
        help="Write plaintext transcript to this path.",
    ),
    session_dir: str | None = typer.Option(default=None),
) -> None:
    """Export a saved transcript to plaintext."""
    settings = Settings()
    if session_dir is not None:
        settings.session_dir = settings.session_dir.__class__(session_dir)
    transcript, session_path = load_selected_session(
        settings.session_dir,
        name=session,
        index=index,
    )
    if session_path is None:
        console.print("No saved transcript found.")
        raise typer.Exit(code=1)

    export_path = default_export_path(session_path)
    if output is not None:
        candidate = Path(output)
        export_path = (
            candidate
            if candidate.is_absolute()
            else session_path.parent / candidate
        )

    transcript.save_plaintext(export_path)
    console.print(f"Exported transcript to {export_path}", soft_wrap=True)


@app.command()
def version() -> None:
    """Print the current version."""
    console.print(__version__)
