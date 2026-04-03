import json

from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.file_tools import ReadFileArgs, ReadFileTool
from nano_claude_code_py.tools.notebook_tools import (
    NotebookEditArgs,
    NotebookEditTool,
)


def test_notebook_edit_replace_updates_source_and_clears_outputs(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"language_info": {"name": "python"}},
                "cells": [
                    {
                        "id": "cell-a",
                        "cell_type": "code",
                        "source": 'print("hello")\n',
                        "execution_count": 3,
                        "outputs": [{"output_type": "stream", "text": "hello\n"}],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = NotebookEditTool().run(
        NotebookEditArgs(
            notebook_path=str(path),
            cell_id="cell-a",
            new_source='print("updated")\n',
        ),
        ctx,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    cell = saved["cells"][0]
    assert not result.is_error
    assert result.content == 'Updated cell cell-a with print("updated")\n'
    assert cell["source"] == 'print("updated")\n'
    assert cell["execution_count"] is None
    assert cell["outputs"] == []


def test_notebook_edit_insert_creates_new_cell_after_target(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {},
                "cells": [
                    {
                        "id": "cell-a",
                        "cell_type": "markdown",
                        "source": "# Title\n",
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = NotebookEditTool().run(
        NotebookEditArgs(
            notebook_path=str(path),
            cell_id="cell-a",
            new_source="## Inserted\n",
            cell_type="markdown",
            edit_mode="insert",
        ),
        ctx,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    inserted = saved["cells"][1]
    assert not result.is_error
    assert isinstance(result.content, str)
    assert result.content.startswith("Inserted cell ")
    assert inserted["cell_type"] == "markdown"
    assert inserted["source"] == "## Inserted\n"
    assert inserted["id"]


def test_notebook_edit_delete_supports_cell_index_fallback(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        json.dumps(
            {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {},
                "cells": [
                    {
                        "id": "cell-a",
                        "cell_type": "markdown",
                        "source": "one\n",
                        "metadata": {},
                    },
                    {
                        "id": "cell-b",
                        "cell_type": "markdown",
                        "source": "two\n",
                        "metadata": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = NotebookEditTool().run(
        NotebookEditArgs(
            notebook_path=str(path),
            cell_id="cell-1",
            new_source="",
            edit_mode="delete",
        ),
        ctx,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert not result.is_error
    assert result.content == "Deleted cell cell-1"
    assert len(saved["cells"]) == 1
    assert saved["cells"][0]["id"] == "cell-a"


def test_notebook_edit_rejects_non_notebook_paths_with_fileedit_message(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = NotebookEditTool().run(
        NotebookEditArgs(
            notebook_path=str(path),
            cell_id="cell-0",
            new_source="x",
        ),
        ctx,
    )

    assert result.is_error
    assert "use the FileEdit tool." in result.content


def test_notebook_edit_requires_prior_read(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        json.dumps({"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []}),
        encoding="utf-8",
    )
    ctx = ToolContext(cwd=tmp_path)

    result = NotebookEditTool().run(
        NotebookEditArgs(
            notebook_path=str(path),
            cell_id="cell-0",
            new_source="x",
        ),
        ctx,
    )

    assert result.is_error
    assert "Read it first before writing to it." in result.content
