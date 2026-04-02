from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class ToolContext(BaseModel):
    cwd: Path


class ToolResult(BaseModel):
    content: str
    is_error: bool = False


class Tool(Protocol):
    name: str
    description: str
    args_model: type[BaseModel]
    is_readonly: bool

    def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        """Execute the tool."""
