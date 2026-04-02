from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.file_tools import (
    EditFileArgs,
    EditFileTool,
    GrepArgs,
    GrepTool,
    ListFilesArgs,
    ListFilesTool,
    ReadFileArgs,
    ReadFileTool,
    WriteFileArgs,
    WriteFileTool,
    closest_lines_hint,
)


def test_write_and_read_file(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    WriteFileTool().run(WriteFileArgs(path="demo.txt", content="hello"), ctx)
    result = ReadFileTool().run(ReadFileArgs(path="demo.txt"), ctx)

    assert result.content == "hello"


def test_edit_file(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello world", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = EditFileTool().run(
        EditFileArgs(path="demo.txt", old_text="world", new_text="agent"),
        ctx,
    )

    assert not result.is_error
    assert path.read_text(encoding="utf-8") == "hello agent"


def test_list_files(tmp_path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = ListFilesTool().run(ListFilesArgs(path=".", pattern="*.py"), ctx)

    assert result.content == "a.py"


def test_grep_finds_matching_lines(tmp_path):
    (tmp_path / "demo.py").write_text("alpha\nbeta\nalpha beta\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(GrepArgs(pattern="alpha", path="."), ctx)

    assert "demo.py:1: alpha" in result.content
    assert "demo.py:3: alpha beta" in result.content


def test_edit_file_reports_helpful_hint_when_text_is_missing(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello world\nhello agent\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = EditFileTool().run(
        EditFileArgs(path="demo.txt", old_text="hello user", new_text="x"),
        ctx,
    )

    assert result.is_error
    assert "Could not find target text" in result.content
    assert "Possible nearby lines" in result.content


def test_closest_lines_hint_returns_fallback_for_no_matches():
    hint = closest_lines_hint("alpha\nbeta\n", "gamma")
    assert "No similar nearby lines were found." in hint
