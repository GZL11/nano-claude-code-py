from __future__ import annotations

from collections.abc import Iterable

from nano_claude_code_py.tools.base import Tool


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._tools)

    def list_tools(self) -> list[Tool]:
        return [self._tools[name] for name in self.list_names()]

    def tool_schemas(self) -> list[dict[str, object]]:
        schemas: list[dict[str, object]] = []
        for tool in self.list_tools():
            schema = tool.args_model.model_json_schema()
            schemas.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": schema,
                }
            )
        return schemas


def default_registry() -> ToolRegistry:
    from nano_claude_code_py.tools.file_tools import (
        EditFileTool,
        GlobTool,
        GrepTool,
        ReadFileTool,
        WriteFileTool,
    )
    from nano_claude_code_py.tools.notebook_tools import NotebookEditTool
    from nano_claude_code_py.tools.shell_tools import RunShellTool
    from nano_claude_code_py.tools.todo_tools import TodoWriteTool

    return ToolRegistry(
        [
            ReadFileTool(),
            GlobTool(),
            GrepTool(),
            TodoWriteTool(),
            WriteFileTool(),
            EditFileTool(),
            NotebookEditTool(),
            RunShellTool(),
        ]
    )
