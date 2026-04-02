from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from nano_claude_code_py.models import ChatMessage, ContentBlock, ToolCall


@dataclass
class ModelResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    content_blocks: list[ContentBlock] = field(default_factory=list)
    was_streamed: bool = False


class ModelClient(Protocol):
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        system_prompt: str,
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        """Return the next model response for the current transcript."""

    def stream_complete(
        self,
        messages: list[ChatMessage],
        *,
        system_prompt: str,
        tools: list[dict[str, object]],
        on_text: Callable[[str], None],
    ) -> ModelResponse:
        """Stream text deltas when available and return the final response."""


class AnthropicModelClient:
    def __init__(self, *, api_key: str, model: str, max_tokens: int = 2048) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def _build_client(self):
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "The anthropic package is not installed. Run: pip install -e '.[dev]'"
            ) from exc
        return Anthropic(api_key=self.api_key)

    @staticmethod
    def _payload_messages(messages: list[ChatMessage]) -> list[dict[str, object]]:
        return [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant"}
        ]

    @staticmethod
    def _parse_response(response, *, was_streamed: bool = False) -> ModelResponse:
        blocks: list[ContentBlock] = []
        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text = getattr(block, "text", "")
                blocks.append({"type": "text", "text": text})
                if isinstance(text, str):
                    text_parts.append(text)
            elif block_type == "tool_use":
                tool_input = getattr(block, "input", {})
                block_id = block.id
                name = block.name
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": block_id,
                        "name": name,
                        "input": tool_input,
                    }
                )
                tool_calls.append(
                    ToolCall(id=block_id, name=name, arguments=dict(tool_input))
                )

        return ModelResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=getattr(response, "stop_reason", None),
            content_blocks=blocks,
            was_streamed=was_streamed,
        )

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        system_prompt: str,
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        client = self._build_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=self._payload_messages(messages),
            tools=tools,
        )
        return self._parse_response(response)

    def stream_complete(
        self,
        messages: list[ChatMessage],
        *,
        system_prompt: str,
        tools: list[dict[str, object]],
        on_text: Callable[[str], None],
    ) -> ModelResponse:
        client = self._build_client()
        with client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=self._payload_messages(messages),
            tools=tools,
        ) as stream:
            for text in stream.text_stream:
                on_text(text)
            response = stream.get_final_message()
        return self._parse_response(response, was_streamed=True)
