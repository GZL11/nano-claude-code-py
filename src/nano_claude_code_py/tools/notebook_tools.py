from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from nano_claude_code_py.tools.base import ReadState, ToolContext, ToolResult
from nano_claude_code_py.tools.file_tools import (
    NOTEBOOK_EXTENSION,
    _resolve_path,
)

NotebookCellType = Literal["code", "markdown"]
NotebookEditMode = Literal["replace", "insert", "delete"]


class NotebookEditArgs(BaseModel):
    notebook_path: str = Field(
        description="The absolute path to the Jupyter notebook to edit."
    )
    cell_id: str | None = Field(
        default=None,
        description=(
            "The ID of the cell to edit. For insert, the new cell is added "
            "after this cell, or at the beginning if omitted."
        ),
    )
    new_source: str = Field(
        description="The new source for the cell."
    )
    cell_type: NotebookCellType | None = Field(
        default=None,
        description=(
            "The cell type to use. Required for insert and optional for replace."
        ),
    )
    edit_mode: NotebookEditMode = Field(
        default="replace",
        description="The edit mode: replace, insert, or delete.",
    )


class NotebookEditTool:
    name = "NotebookEdit"
    description = "Replace the contents of a specific cell in a Jupyter notebook."
    args_model = NotebookEditArgs
    is_readonly = False

    def run(self, args: NotebookEditArgs, ctx: ToolContext) -> ToolResult:
        path = _resolve_path(ctx, args.notebook_path, require_absolute=True)
        validation_error = validate_notebook_edit(path, args, ctx)
        if validation_error is not None:
            return validation_error

        original_content = path.read_text(encoding="utf-8")
        try:
            notebook = json.loads(original_content)
        except json.JSONDecodeError:
            return ToolResult(content="Notebook is not valid JSON.", is_error=True)

        cells = notebook["cells"]
        cell_index = resolve_cell_index(cells, args.cell_id)
        if cell_index is None:
            return ToolResult(
                content=f'Cell with ID "{args.cell_id}" not found in notebook.',
                is_error=True,
            )

        edit_mode = args.edit_mode
        if edit_mode == "insert" and args.cell_id is not None:
            cell_index += 1

        output_cell_id = notebook_output_cell_id(
            notebook,
            edit_mode=edit_mode,
            requested_cell_id=args.cell_id,
        )

        if edit_mode == "delete":
            cells.pop(cell_index)
        elif edit_mode == "insert":
            cells.insert(
                cell_index,
                build_notebook_cell(
                    cell_type=args.cell_type or "code",
                    cell_id=output_cell_id or "",
                    new_source=args.new_source,
                ),
            )
        else:
            target_cell = cells[cell_index]
            target_cell["source"] = args.new_source
            if target_cell.get("cell_type") == "code":
                target_cell["execution_count"] = None
                target_cell["outputs"] = []
            if args.cell_type is not None:
                target_cell["cell_type"] = args.cell_type

        updated_content = json.dumps(notebook, indent=1, ensure_ascii=False) + "\n"
        path.write_text(updated_content, encoding="utf-8")
        ctx.read_state[path] = ReadState(
            timestamp_ns=path.stat().st_mtime_ns,
            is_partial=False,
            offset=None,
            limit=None,
            pages=None,
        )

        output_cell_id_text = output_cell_id or "undefined"
        if edit_mode == "replace":
            return ToolResult(
                content=f"Updated cell {output_cell_id_text} with {args.new_source}"
            )
        if edit_mode == "insert":
            return ToolResult(
                content=f"Inserted cell {output_cell_id_text} with {args.new_source}"
            )
        return ToolResult(content=f"Deleted cell {output_cell_id_text}")


def validate_notebook_edit(
    path: Path,
    args: NotebookEditArgs,
    ctx: ToolContext,
) -> ToolResult | None:
    if path.suffix.lower() != NOTEBOOK_EXTENSION:
        return ToolResult(
            content=(
                "File must be a Jupyter notebook (.ipynb file). For editing "
                "other file types, use the FileEdit tool."
            ),
            is_error=True,
        )
    if args.edit_mode == "insert" and args.cell_type is None:
        return ToolResult(
            content="Cell type is required when using edit_mode=insert.",
            is_error=True,
        )
    state = ctx.read_state.get(path)
    if state is None:
        return ToolResult(
            content="File has not been read yet. Read it first before writing to it.",
            is_error=True,
        )
    if not path.exists():
        return ToolResult(content="Notebook file does not exist.", is_error=True)
    if state.is_partial:
        return ToolResult(
            content="File has not been read yet. Read it first before writing to it.",
            is_error=True,
        )
    if state.timestamp_ns is not None and path.stat().st_mtime_ns > state.timestamp_ns:
        return ToolResult(
            content=(
                "File has been modified since read, either by the user or by a "
                "linter. Read it again before attempting to write it."
            ),
            is_error=True,
        )

    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ToolResult(content="Notebook is not valid JSON.", is_error=True)

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        return ToolResult(
            content="Notebook is missing a valid cells array.",
            is_error=True,
        )
    if args.cell_id is None:
        if args.edit_mode != "insert":
            return ToolResult(
                content="Cell ID must be specified when not inserting a new cell.",
                is_error=True,
            )
        return None

    cell_index = resolve_cell_index(cells, args.cell_id)
    if cell_index is not None:
        return None

    parsed_index = parse_cell_id(args.cell_id)
    if parsed_index is not None:
        return ToolResult(
            content=f"Cell with index {parsed_index} does not exist in notebook.",
            is_error=True,
        )
    return ToolResult(
        content=f'Cell with ID "{args.cell_id}" not found in notebook.',
        is_error=True,
    )


def resolve_cell_index(cells: list[object], cell_id: str | None) -> int | None:
    if cell_id is None:
        return 0
    for index, cell in enumerate(cells):
        if isinstance(cell, dict) and cell.get("id") == cell_id:
            return index
    parsed_index = parse_cell_id(cell_id)
    if parsed_index is None:
        return None
    if 0 <= parsed_index < len(cells):
        return parsed_index
    return None


def parse_cell_id(cell_id: str) -> int | None:
    if not cell_id.startswith("cell-"):
        return None
    suffix = cell_id.removeprefix("cell-")
    if not suffix.isdigit():
        return None
    return int(suffix)


def create_notebook_cell_id(notebook: dict[str, object]) -> str:
    nbformat = notebook.get("nbformat")
    nbformat_minor = notebook.get("nbformat_minor")
    if isinstance(nbformat, int) and (
        nbformat > 4
        or (
            nbformat == 4
            and isinstance(nbformat_minor, int)
            and nbformat_minor >= 5
        )
    ):
        return uuid.uuid4().hex[:13]
    return ""


def notebook_output_cell_id(
    notebook: dict[str, object],
    *,
    edit_mode: NotebookEditMode,
    requested_cell_id: str | None,
) -> str | None:
    if not notebook_supports_cell_ids(notebook):
        return None
    if edit_mode == "insert":
        return create_notebook_cell_id(notebook)
    return requested_cell_id


def notebook_supports_cell_ids(notebook: dict[str, object]) -> bool:
    nbformat = notebook.get("nbformat")
    nbformat_minor = notebook.get("nbformat_minor")
    if not isinstance(nbformat, int):
        return False
    if nbformat > 4:
        return True
    return nbformat == 4 and isinstance(nbformat_minor, int) and nbformat_minor >= 5


def build_notebook_cell(
    *,
    cell_type: NotebookCellType,
    cell_id: str,
    new_source: str,
) -> dict[str, object]:
    if cell_type == "markdown":
        cell: dict[str, object] = {
            "cell_type": "markdown",
            "metadata": {},
            "source": new_source,
        }
        if cell_id:
            cell["id"] = cell_id
        return cell

    cell = {
        "cell_type": "code",
        "metadata": {},
        "source": new_source,
        "execution_count": None,
        "outputs": [],
    }
    if cell_id:
        cell["id"] = cell_id
    return cell
