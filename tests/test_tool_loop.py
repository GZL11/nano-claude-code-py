from rich.console import Console

from nano_claude_code_py.llm.client import ModelResponse
from nano_claude_code_py.llm.tool_loop import (
    run_turn,
    tool_result_preview,
)
from nano_claude_code_py.models import ChatMessage, ToolCall
from nano_claude_code_py.permissions import PermissionManager
from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.registry import default_registry


class StubClient:
    def __init__(self, file_path: str) -> None:
        self.calls = 0
        self.file_path = file_path

    def complete(self, messages, *, system_prompt, tools):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="toolu_1",
                        name="Write",
                        arguments={
                            "file_path": self.file_path,
                            "content": "hello",
                        },
                    )
                ],
                stop_reason="tool_use",
                content_blocks=[
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "Write",
                        "input": {
                            "file_path": self.file_path,
                            "content": "hello",
                        },
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


class BashStubClient:
    def __init__(self, command: str) -> None:
        self.calls = 0
        self.command = command

    def complete(self, messages, *, system_prompt, tools):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="toolu_bash_1",
                        name="Bash",
                        arguments={"command": self.command},
                    )
                ],
                stop_reason="tool_use",
                content_blocks=[
                    {
                        "type": "tool_use",
                        "id": "toolu_bash_1",
                        "name": "Bash",
                        "input": {"command": self.command},
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


class TodoStubClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, *, system_prompt, tools):
        self.calls += 1
        if self.calls == 1:
            todo_input = {
                "todos": [
                    {
                        "content": "Write tests",
                        "status": "in_progress",
                        "activeForm": "Writing tests",
                    }
                ]
            }
            return ModelResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="toolu_todo_1",
                        name="TodoWrite",
                        arguments=todo_input,
                    )
                ],
                stop_reason="tool_use",
                content_blocks=[
                    {
                        "type": "tool_use",
                        "id": "toolu_todo_1",
                        "name": "TodoWrite",
                        "input": todo_input,
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
    output_path = tmp_path / "out.txt"
    response = run_turn(
        StubClient(str(output_path)),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="danger-full-access"),
    )

    assert response.text == "done"
    assert output_path.read_text(encoding="utf-8") == "hello"
    assert messages[-1].role == "assistant"


def test_run_turn_respects_permission_denial(tmp_path):
    messages = [ChatMessage(role="user", content="write a file")]
    output_path = tmp_path / "out.txt"
    response = run_turn(
        StubClient(str(output_path)),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="ask", prompt=lambda _: False),
    )

    assert response.text == "done"
    assert not (tmp_path / "out.txt").exists()
    assert messages[-2].role == "user"
    assert (
        messages[-2].content[0]["content"]
        == f"Permission denied for: Write [write/exec] {output_path}"
    )


def test_run_turn_streams_text(tmp_path):
    chunks: list[str] = []
    messages = [ChatMessage(role="user", content="say done")]
    output_path = tmp_path / "out.txt"

    response = run_turn(
        StubClient(str(output_path)),
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


def test_tool_result_preview_summarizes_image_blocks():
    preview = tool_result_preview(
        [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": "abc",
                },
            }
        ]
    )

    assert preview == "[image image/png]"


def test_tool_result_preview_normalizes_newlines_in_text_blocks():
    preview = tool_result_preview(
        [
            {
                "type": "text",
                "text": "alpha\nbeta",
            }
        ]
    )

    assert preview == "alpha beta"


def test_run_turn_allows_readonly_bash_in_accept_edits_mode(tmp_path):
    messages = [ChatMessage(role="user", content="show the current directory")]

    response = run_turn(
        BashStubClient("pwd"),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="acceptEdits"),
    )

    assert response.text == "done"
    assert messages[-2].role == "user"
    assert "Permission denied" not in str(messages[-2].content)


def test_run_turn_rejects_write_outside_cwd_in_accept_edits_mode(tmp_path):
    messages = [ChatMessage(role="user", content="write a file")]
    output_path = tmp_path.parent / "outside.txt"

    response = run_turn(
        StubClient(str(output_path)),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="acceptEdits"),
    )

    assert response.text == "done"
    assert not output_path.exists()
    assert messages[-2].role == "user"
    assert (
        messages[-2].content[0]["content"]
        == f"Permission denied for: Write [write/exec] {output_path}"
    )


def test_run_turn_prompts_for_write_outside_cwd_in_accept_edits_mode(tmp_path):
    messages = [ChatMessage(role="user", content="write a file")]
    output_path = tmp_path.parent / "outside-prompted.txt"

    response = run_turn(
        StubClient(str(output_path)),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(
            mode="acceptEdits",
            prompt=lambda _: True,
        ),
    )

    assert response.text == "done"
    assert output_path.read_text(encoding="utf-8") == "hello"


def test_run_turn_uses_request_summary_in_permission_denial(tmp_path):
    messages = [ChatMessage(role="user", content="write a file")]
    output_path = tmp_path / "out.txt"
    response = run_turn(
        StubClient(str(output_path)),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="ask", prompt=lambda _: False),
    )

    assert response.text == "done"
    assert messages[-2].role == "user"
    assert (
        messages[-2].content[0]["content"]
        == f"Permission denied for: Write [write/exec] {output_path}"
    )


def test_run_turn_hides_todowrite_console_activity(tmp_path):
    messages = [ChatMessage(role="user", content="track progress")]
    console = Console(record=True, force_terminal=False)

    response = run_turn(
        TodoStubClient(),
        default_registry(),
        messages,
        system_prompt="test",
        tool_context=ToolContext(cwd=tmp_path),
        permission_manager=PermissionManager(mode="danger-full-access"),
        console=console,
    )

    assert response.text == "done"
    assert messages[-2].role == "user"
    assert messages[-2].content[0]["type"] == "tool_result"

    rendered = console.export_text()
    assert "TodoWrite" not in rendered
    assert "tool request" not in rendered
    assert "tool result" not in rendered
