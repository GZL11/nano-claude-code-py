from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from nano_claude_code_py.models import ChatMessage, Role


@dataclass
class SessionTranscript:
    messages: list[ChatMessage] = field(default_factory=list)

    def add(
        self,
        role: Role,
        content: str | list[dict[str, object]],
    ) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    def clear(self) -> None:
        self.messages.clear()

    def save_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for message in self.messages:
                handle.write(message.model_dump_json())
                handle.write("\n")

    def to_plaintext(self) -> str:
        if not self.messages:
            return ""
        chunks: list[str] = []
        for index, message in enumerate(self.messages, start=1):
            chunks.append(f"## {index}. {message.role}")
            chunks.append(message.text_content() or "[non-text content]")
            chunks.append("")
        return "\n".join(chunks).rstrip() + "\n"

    def save_plaintext(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_plaintext(), encoding="utf-8")

    @classmethod
    def load_jsonl(cls, path: Path) -> SessionTranscript:
        transcript = cls()
        if not path.exists():
            return transcript
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                transcript.messages.append(ChatMessage.model_validate_json(line))
        return transcript


def default_session_path(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    return root / f"{stamp}.jsonl"


@dataclass(frozen=True)
class SessionInfo:
    path: Path
    message_count: int
    updated_at: datetime
    preview: str


def latest_session_path(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = sorted(root.glob("*.jsonl"))
    if not candidates:
        return None
    return candidates[-1]


def load_latest_session(root: Path) -> tuple[SessionTranscript, Path | None]:
    path = latest_session_path(root)
    if path is None:
        return SessionTranscript(), None
    return SessionTranscript.load_jsonl(path), path


def list_sessions(root: Path) -> list[SessionInfo]:
    if not root.exists():
        return []

    sessions: list[SessionInfo] = []
    for path in sorted(root.glob("*.jsonl"), reverse=True):
        transcript = SessionTranscript.load_jsonl(path)
        preview = ""
        for message in transcript.messages:
            if message.role == "user":
                preview = message.text_content()
                if preview:
                    break
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        sessions.append(
            SessionInfo(
                path=path,
                message_count=len(transcript.messages),
                updated_at=updated_at,
                preview=preview[:80],
            )
        )
    return sessions


def load_selected_session(
    root: Path,
    *,
    name: str | None = None,
    index: int | None = None,
) -> tuple[SessionTranscript, Path | None]:
    sessions = list_sessions(root)
    if not sessions:
        return SessionTranscript(), None

    if name is not None:
        for session in sessions:
            if session.path.name == name or session.path.stem == name:
                return SessionTranscript.load_jsonl(session.path), session.path
        return SessionTranscript(), None

    if index is not None:
        if index < 1 or index > len(sessions):
            return SessionTranscript(), None
        session = sessions[index - 1]
        return SessionTranscript.load_jsonl(session.path), session.path

    session = sessions[0]
    return SessionTranscript.load_jsonl(session.path), session.path


def default_export_path(session_path: Path) -> Path:
    return session_path.with_suffix(".txt")
