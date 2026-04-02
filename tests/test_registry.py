from pydantic import BaseModel

from nano_claude_code_py.tools.base import ToolContext, ToolResult
from nano_claude_code_py.tools.registry import ToolRegistry


class DummyArgs(BaseModel):
    value: str


class DummyTool:
    name = "dummy"
    description = "dummy tool"
    args_model = DummyArgs
    is_readonly = True

    def run(self, args: DummyArgs, ctx: ToolContext) -> ToolResult:
        return ToolResult(content=f"{ctx.cwd}:{args.value}")


def test_registry_registers_and_lists_tools(tmp_path):
    registry = ToolRegistry()
    registry.register(DummyTool())

    assert registry.get("dummy") is not None
    assert registry.list_names() == ["dummy"]
