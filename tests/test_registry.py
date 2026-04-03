from pydantic import BaseModel

from nano_claude_code_py.tools.base import ToolContext, ToolResult
from nano_claude_code_py.tools.registry import ToolRegistry, default_registry


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


def test_default_registry_exposes_source_aligned_tool_descriptions():
    registry = default_registry()
    schemas = {schema["name"]: schema for schema in registry.tool_schemas()}

    assert (
        schemas["Read"]["description"].startswith(
            "Reads a file from the local filesystem."
        )
    )
    assert "The file_path parameter must be an absolute path" in schemas["Read"][
        "description"
    ]
    assert "This tool can read Jupyter notebooks" in schemas["Read"]["description"]
    assert "This tool can read PDF files" in schemas["Read"]["description"]
    assert "matching file paths sorted by modification time" in schemas["Glob"][
        "description"
    ]
    assert "Prefer Edit" in schemas["Write"]["description"]
    assert "README files unless explicitly requested" in schemas["Write"][
        "description"
    ]
    assert "replace_all" in schemas["Edit"]["description"]
    assert "NEVER write new files unless explicitly required" in schemas["Edit"][
        "description"
    ]
    assert "track progress and pending tasks" in schemas["TodoWrite"]["description"]
    assert (
        schemas["NotebookEdit"]["description"]
        == "Replace the contents of a specific cell in a Jupyter notebook."
    )
    assert "ripgrep" in schemas["Grep"]["description"]
    assert "NEVER invoke `grep` or `rg` as a Bash command" in schemas["Grep"][
        "description"
    ]
    assert schemas["Bash"]["description"] == "Run shell command"
    read_file_path = schemas["Read"]["input_schema"]["properties"]["file_path"]
    todo_items = schemas["TodoWrite"]["input_schema"]["properties"]["todos"]
    bash_background = schemas["Bash"]["input_schema"]["properties"][
        "run_in_background"
    ]
    bash_timeout = schemas["Bash"]["input_schema"]["properties"]["timeout"]
    assert "absolute path" in read_file_path["description"]
    assert todo_items["description"] == "The updated todo list"
    assert "Use Read to read the output later." in bash_background["description"]
    assert "Optional timeout in milliseconds" in bash_timeout["description"]
    assert (
        "dangerouslyDisableSandbox"
        not in schemas["Bash"]["input_schema"]["properties"]
    )
