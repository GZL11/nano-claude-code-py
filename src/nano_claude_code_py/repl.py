from pathlib import Path

from rich.console import Console

from nano_claude_code_py.config import Settings
from nano_claude_code_py.llm.client import AnthropicModelClient
from nano_claude_code_py.llm.tool_loop import run_turn
from nano_claude_code_py.permissions import PermissionManager
from nano_claude_code_py.prompts import build_system_prompt
from nano_claude_code_py.session import (
    SessionTranscript,
    default_export_path,
    default_session_path,
    list_sessions,
)
from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.registry import default_registry

console = Console()
DEFAULT_HISTORY_LIMIT = 10
HELP_TEXT = (
    "/help  /clear  /tools  /sessions  /session  /history [n]  /save  "
    "/export [path]  /exit"
)


def run_repl(
    settings: Settings,
    *,
    transcript: SessionTranscript | None = None,
    session_path=None,
) -> None:
    transcript = transcript or SessionTranscript()
    registry = default_registry()
    session_path = session_path or default_session_path(settings.session_dir)
    tool_context = ToolContext(cwd=settings.cwd)
    console.print("[bold]nano-claude-code-py[/bold]")
    console.print("Type /help for commands. Type /exit to quit.")
    if transcript.messages:
        console.print(
            f"Resumed transcript with {len(transcript.messages)} message(s)."
        )

    while True:
        try:
            prompt = input("> ").strip()
        except EOFError:
            console.print()
            break

        if not prompt:
            continue
        if prompt.startswith("/"):
            if handle_local_command(
                prompt,
                transcript=transcript,
                settings=settings,
                session_path=session_path,
                cwd=settings.cwd,
                registry=registry,
            ):
                if prompt == "/exit":
                    break
            continue

        transcript.add("user", prompt)
        transcript.save_jsonl(session_path)
        if not settings.anthropic_api_key:
            console.print(
                "[red]ANTHROPIC_API_KEY is not set.[/red] "
                "The transcript was updated, but the model was not called."
            )
            continue

        client = AnthropicModelClient(
            api_key=settings.anthropic_api_key,
            model=settings.model,
        )
        permission_manager = PermissionManager(
            mode=settings.permission_mode,
            prompt=lambda summary: console.input(
                format_permission_prompt(summary)
            ).strip().lower()
            in {"y", "yes"},
        )
        response = run_turn(
            client,
            registry,
            transcript.messages,
            system_prompt=build_system_prompt(settings.language),
            tool_context=tool_context,
            permission_manager=permission_manager,
            console=console,
            on_text=lambda text: console.print(text, end=""),
            stream=True,
        )
        if response.text and not response.was_streamed:
            console.print(response.text)
        transcript.save_jsonl(session_path)


def handle_local_command(
    prompt: str,
    *,
    transcript: SessionTranscript,
    settings: Settings,
    session_path,
    cwd,
    registry,
) -> bool:
    if prompt == "/exit":
        return True
    if prompt == "/clear":
        transcript.clear()
        transcript.save_jsonl(session_path)
        console.print("Transcript cleared.")
        return True
    if prompt == "/help":
        console.print(HELP_TEXT, markup=False)
        return True
    if prompt == "/tools":
        console.print("\n".join(registry.list_names()))
        return True
    if prompt == "/sessions":
        sessions = list_sessions(settings.session_dir)
        if not sessions:
            console.print("No saved sessions.")
        else:
            for idx, session in enumerate(sessions, start=1):
                console.print(
                    f"{idx}. {session.path.name}  "
                    f"messages={session.message_count}  "
                    f"preview={session.preview or '-'}"
                )
        return True
    if prompt == "/session":
        console.print(render_session_summary(transcript, session_path, cwd))
        return True
    if prompt == "/save":
        transcript.save_jsonl(session_path)
        console.print(f"Saved transcript to {session_path}")
        return True
    if prompt.startswith("/export"):
        export_path = parse_export_path(prompt, session_path)
        transcript.save_plaintext(export_path)
        console.print(f"Exported transcript to {export_path}")
        return True
    if prompt.startswith("/history"):
        console.print(render_history(transcript, parse_history_limit(prompt)))
        return True
    return False


def parse_history_limit(prompt: str) -> int:
    parts = prompt.split()
    if len(parts) < 2:
        return DEFAULT_HISTORY_LIMIT
    try:
        value = int(parts[1])
    except ValueError:
        return DEFAULT_HISTORY_LIMIT
    return max(1, min(value, 100))


def parse_export_path(prompt: str, session_path: Path) -> Path:
    parts = prompt.split(maxsplit=1)
    if len(parts) < 2:
        return default_export_path(session_path)
    return session_path.parent / parts[1]


def render_history(transcript: SessionTranscript, limit: int) -> str:
    if not transcript.messages:
        return "No messages in the current transcript."

    selected = transcript.messages[-limit:]
    lines: list[str] = []
    start_index = len(transcript.messages) - len(selected) + 1
    for offset, message in enumerate(selected, start=start_index):
        text = message.text_content().replace("\n", " ").strip()
        if len(text) > 120:
            text = text[:117] + "..."
        lines.append(f"{offset}. {message.role}: {text or '[non-text content]'}")
    return "\n".join(lines)


def render_session_summary(transcript: SessionTranscript, session_path, cwd) -> str:
    return (
        f"session_file: {session_path}\n"
        f"message_count: {len(transcript.messages)}\n"
        f"workspace: {cwd}"
    )


def format_permission_prompt(summary: str) -> str:
    return f"Permission: {summary} [y/N] "
