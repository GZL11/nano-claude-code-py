from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

ToolResultContent = str | list[dict[str, object]]


@dataclass
class ReadState:
    timestamp_ns: int | None
    is_partial: bool = False
    offset: int | None = None
    limit: int | None = None
    pages: str | None = None


@dataclass
class ToolContext:
    cwd: Path
    read_state: dict[Path, ReadState] = field(default_factory=dict)
    todos: list[dict[str, str]] = field(default_factory=list)


class ToolResult(BaseModel):
    content: ToolResultContent
    is_error: bool = False


class Tool(Protocol):
    name: str
    description: str
    args_model: type[BaseModel]
    is_readonly: bool

    def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        """Execute the tool."""
