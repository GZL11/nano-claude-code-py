from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.todo_tools import (
    TODO_WRITE_SUCCESS_MESSAGE,
    TodoWriteArgs,
    TodoWriteTool,
)


def test_todo_write_stores_incomplete_todos_in_context(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = TodoWriteTool().run(
        TodoWriteArgs(
            todos=[
                {
                    "content": "Run tests",
                    "status": "in_progress",
                    "activeForm": "Running tests",
                },
                {
                    "content": "Summarize changes",
                    "status": "pending",
                    "activeForm": "Summarizing changes",
                },
            ]
        ),
        ctx,
    )

    assert not result.is_error
    assert result.content == TODO_WRITE_SUCCESS_MESSAGE
    assert ctx.todos == [
        {
            "content": "Run tests",
            "status": "in_progress",
            "activeForm": "Running tests",
        },
        {
            "content": "Summarize changes",
            "status": "pending",
            "activeForm": "Summarizing changes",
        },
    ]


def test_todo_write_clears_context_when_all_todos_completed(tmp_path):
    ctx = ToolContext(
        cwd=tmp_path,
        todos=[
            {
                "content": "Existing task",
                "status": "in_progress",
                "activeForm": "Working on existing task",
            }
        ],
    )

    TodoWriteTool().run(
        TodoWriteArgs(
            todos=[
                {
                    "content": "Run tests",
                    "status": "completed",
                    "activeForm": "Running tests",
                }
            ]
        ),
        ctx,
    )

    assert ctx.todos == []
