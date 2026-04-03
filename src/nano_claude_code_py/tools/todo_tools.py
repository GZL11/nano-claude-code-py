from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from nano_claude_code_py.tools.base import ToolContext, ToolResult

TodoStatus = Literal["pending", "in_progress", "completed"]
TODO_WRITE_SUCCESS_MESSAGE = (
    "Todos have been modified successfully. Ensure that you continue to use "
    "the todo list to track your progress. Please proceed with the current "
    "tasks if applicable"
)


class TodoItem(BaseModel):
    content: str = Field(min_length=1, description="Content cannot be empty")
    status: TodoStatus
    activeForm: str = Field(
        min_length=1,
        description="Active form cannot be empty",
    )


class TodoWriteArgs(BaseModel):
    todos: list[TodoItem] = Field(description="The updated todo list")


class TodoWriteTool:
    name = "TodoWrite"
    description = (
        "Update the todo list for the current session. To be used proactively "
        "and often to track progress and pending tasks. Make sure that at "
        "least one task is in_progress at all times. Always provide both "
        "content (imperative) and activeForm (present continuous) for each "
        "task."
    )
    args_model = TodoWriteArgs
    is_readonly = False

    def run(self, args: TodoWriteArgs, ctx: ToolContext) -> ToolResult:
        all_done = all(todo.status == "completed" for todo in args.todos)
        ctx.todos = [] if all_done else [todo.model_dump() for todo in args.todos]
        return ToolResult(content=TODO_WRITE_SUCCESS_MESSAGE)
