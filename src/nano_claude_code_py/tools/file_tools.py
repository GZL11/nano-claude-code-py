from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel

from nano_claude_code_py.tools.base import ToolContext, ToolResult


def _resolve_path(ctx: ToolContext, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ctx.cwd / path
    resolved = path.resolve()
    try:
        resolved.relative_to(ctx.cwd.resolve())
    except ValueError as exc:
        raise PermissionError(f"Path {resolved} is outside the workspace") from exc
    return resolved


class ReadFileArgs(BaseModel):
    path: str


class ReadFileTool:
    name = "read_file"
    description = "Read a single file from disk."
    args_model = ReadFileArgs
    is_readonly = True

    def run(self, args: ReadFileArgs, ctx: ToolContext) -> ToolResult:
        path = _resolve_path(ctx, args.path)
        return ToolResult(content=path.read_text(encoding="utf-8"))


class ListFilesArgs(BaseModel):
    path: str = "."
    pattern: str = "*"


class ListFilesTool:
    name = "list_files"
    description = "List files under a directory with a glob pattern."
    args_model = ListFilesArgs
    is_readonly = True

    def run(self, args: ListFilesArgs, ctx: ToolContext) -> ToolResult:
        root = _resolve_path(ctx, args.path)
        matches = [
            str(path.relative_to(ctx.cwd))
            for path in sorted(root.glob(args.pattern))
        ]
        return ToolResult(content="\n".join(matches))


class GrepArgs(BaseModel):
    pattern: str
    path: str = "."


class GrepTool:
    name = "grep"
    description = "Search for a regular expression in text files under a directory."
    args_model = GrepArgs
    is_readonly = True

    def run(self, args: GrepArgs, ctx: ToolContext) -> ToolResult:
        root = _resolve_path(ctx, args.path)
        regex = re.compile(args.pattern)
        matches: list[str] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for index, line in enumerate(content.splitlines(), start=1):
                if regex.search(line):
                    matches.append(
                        f"{path.relative_to(ctx.cwd)}:{index}: {line}"
                    )
        return ToolResult(content="\n".join(matches))


class WriteFileArgs(BaseModel):
    path: str
    content: str


class WriteFileTool:
    name = "write_file"
    description = "Write content to a file, creating parent directories if needed."
    args_model = WriteFileArgs
    is_readonly = False

    def run(self, args: WriteFileArgs, ctx: ToolContext) -> ToolResult:
        try:
            path = _resolve_path(ctx, args.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(
                content=f"Failed to write {args.path}: {exc}",
                is_error=True,
            )
        return ToolResult(content=f"Wrote {path}")


class EditFileArgs(BaseModel):
    path: str
    old_text: str
    new_text: str


class EditFileTool:
    name = "edit_file"
    description = "Replace a text snippet in a file."
    args_model = EditFileArgs
    is_readonly = False

    def run(self, args: EditFileArgs, ctx: ToolContext) -> ToolResult:
        try:
            path = _resolve_path(ctx, args.path)
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return ToolResult(
                content=f"Failed to read {args.path}: {exc}",
                is_error=True,
            )
        if args.old_text not in content:
            hint = closest_lines_hint(content, args.old_text)
            return ToolResult(
                content=(
                    f"Could not find target text in {path}.\n"
                    f"Target preview: {truncate_preview(args.old_text)}\n"
                    f"{hint}"
                ),
                is_error=True,
            )
        updated = content.replace(args.old_text, args.new_text, 1)
        try:
            path.write_text(updated, encoding="utf-8")
        except Exception as exc:
            return ToolResult(
                content=f"Failed to write {args.path}: {exc}",
                is_error=True,
            )
        return ToolResult(content=f"Edited {path}")


def truncate_preview(text: str, limit: int = 80) -> str:
    single_line = text.replace("\n", "\\n")
    if len(single_line) <= limit:
        return single_line
    return single_line[: limit - 3] + "..."


def closest_lines_hint(content: str, target: str, max_lines: int = 3) -> str:
    target_lines = [line.strip() for line in target.splitlines() if line.strip()]
    if not target_lines:
        return "No target lines were provided."

    anchors = target_lines[:max_lines]
    source_lines = content.splitlines()
    scored_matches: list[tuple[float, int, str]] = []
    for index, line in enumerate(source_lines, start=1):
        stripped = line.strip()
        score = max(
            (
                SequenceMatcher(a=anchor, b=stripped).ratio()
                for anchor in anchors
            ),
            default=0.0,
        )
        if any(anchor in stripped or stripped in anchor for anchor in anchors):
            score = max(score, 1.0)
        if score >= 0.45:
            scored_matches.append((score, index, line))

    if scored_matches:
        scored_matches.sort(key=lambda item: (-item[0], item[1]))
        matches = [
            f"Nearby line {index}: {line}"
            for _, index, line in scored_matches[:max_lines]
        ]
        return "Possible nearby lines:\n" + "\n".join(matches)
    return "No similar nearby lines were found."
