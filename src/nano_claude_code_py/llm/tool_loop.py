from __future__ import annotations

from collections.abc import Callable

from rich.console import Console

from nano_claude_code_py.llm.client import ModelClient, ModelResponse
from nano_claude_code_py.models import ChatMessage
from nano_claude_code_py.permissions import PermissionManager, summarize_tool_request
from nano_claude_code_py.tools.base import ToolContext, ToolResult
from nano_claude_code_py.tools.registry import ToolRegistry


def run_turn(
    client: ModelClient,
    registry: ToolRegistry,
    messages: list[ChatMessage],
    *,
    system_prompt: str,
    tool_context: ToolContext,
    permission_manager: PermissionManager,
    console: Console | None = None,
    on_text: Callable[[str], None] | None = None,
    stream: bool = False,
    max_iterations: int = 8,
) -> ModelResponse:
    """Execute one model turn.
    """
    for _ in range(max_iterations):
        if stream:
            response = client.stream_complete(
                messages,
                system_prompt=system_prompt,
                tools=registry.tool_schemas(),
                on_text=on_text or (lambda _: None),
            )
        else:
            response = client.complete(
                messages,
                system_prompt=system_prompt,
                tools=registry.tool_schemas(),
            )
        assistant_blocks = response.content_blocks or [
            {"type": "text", "text": response.text}
        ]
        messages.append(ChatMessage(role="assistant", content=assistant_blocks))

        if not response.tool_calls:
            return response

        tool_result_blocks: list[dict[str, object]] = []
        for tool_call in response.tool_calls:
            tool = registry.get(tool_call.name)
            if tool is None:
                if console is not None:
                    console.print(f"[red]unknown tool[/red] {tool_call.name}")
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": f"Unknown tool: {tool_call.name}",
                        "is_error": True,
                    }
                )
                continue

            summary = summarize_tool_request(tool, tool_call.arguments)
            if console is not None:
                console.print(f"[bold blue]tool request[/bold blue] {summary}")
            if not permission_manager.allow(tool, summary):
                if console is not None:
                    console.print(f"[yellow]tool denied[/yellow] {tool.name}")
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": f"Permission denied for tool {tool.name}",
                        "is_error": True,
                    }
                )
                continue

            try:
                args = tool.args_model.model_validate(tool_call.arguments)
                if console is not None:
                    console.print(f"[cyan]running[/cyan] {tool.name}")
                result = tool.run(args, tool_context)
            except Exception as exc:
                result = tool_context_error(str(exc))

            if console is not None:
                style = "red" if result.is_error else "green"
                preview = result.content.replace("\n", " ")[:140]
                console.print(f"[{style}]tool result[/{style}] {tool.name}: {preview}")

            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result.content,
                    "is_error": result.is_error,
                }
            )

        messages.append(ChatMessage(role="user", content=tool_result_blocks))
        if stream and on_text is not None and response.was_streamed:
            on_text("\n")

    raise RuntimeError("Model exceeded the maximum tool loop iterations")


def tool_context_error(message: str) -> ToolResult:
    return ToolResult(content=message, is_error=True)
