from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]
ContentBlock = dict[str, object]


class ChatMessage(BaseModel):
    role: Role
    content: str | list[ContentBlock]

    def text_content(self) -> str:
        if isinstance(self.content, str):
            return self.content
        parts: list[str] = []
        for block in self.content:
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    call_id: str
    name: str
    content: str
    is_error: bool = False
