from nano_claude_code_py.llm.client import ModelResponse
from nano_claude_code_py.llm.tool_loop import run_turn
from nano_claude_code_py.models import ChatMessage, ToolCall
from nano_claude_code_py.permissions import PermissionManager
from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.registry import default_registry


class StubClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, *, system_prompt, tools):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="toolu_1",
                        name="write_file",
                        arguments={"path": "out.txt", "content": "hello"},
                    )
                ],
                stop_reason="tool_use",
                content_blocks=[
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "write_file",
                        "input": {"path": "out.txt", "content": "hello"},
                    }
                ],
            )
        return ModelResponse(
            text="done",
            stop_reason="end_turn",
            content_blocks=[{"type": "text", "text": "done"}],
        )

    def stream_complete(self, messages, *, system_prompt, tools, on_text):
        response = self.complete(
            messages,
            system_prompt=system_prompt,
            tools=tools,
        )
        if response.text:
            on_text(response.text)
            response.was_streamed = True
        return response


def test_run_turn_executes_tool_and_returns_final_text(tmp_path):
    messages = [ChatMessage(role="user", content="write a file")]
    response = run_turn(
        StubClient(),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="danger-full-access"),
    )

    assert response.text == "done"
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hello"
    assert messages[-1].role == "assistant"


def test_run_turn_respects_permission_denial(tmp_path):
    messages = [ChatMessage(role="user", content="write a file")]
    response = run_turn(
        StubClient(),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="ask", prompt=lambda _: False),
    )

    assert response.text == "done"
    assert not (tmp_path / "out.txt").exists()


def test_run_turn_streams_text(tmp_path):
    chunks: list[str] = []
    messages = [ChatMessage(role="user", content="say done")]

    response = run_turn(
        StubClient(),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="danger-full-access"),
        on_text=chunks.append,
        stream=True,
    )

    assert response.was_streamed
    assert "".join(chunks).startswith("done")
