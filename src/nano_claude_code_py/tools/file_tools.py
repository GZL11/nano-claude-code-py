from __future__ import annotations

import base64
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nano_claude_code_py.tools.base import ReadState, ToolContext, ToolResult

MAX_LINES_TO_READ = 2000
DEFAULT_GREP_HEAD_LIMIT = 250
DEFAULT_GLOB_LIMIT = 100
BLOCKED_DEVICE_PATHS = {
    "/dev/zero",
    "/dev/random",
    "/dev/urandom",
    "/dev/full",
    "/dev/stdin",
    "/dev/tty",
    "/dev/console",
    "/dev/stdout",
    "/dev/stderr",
    "/dev/fd/0",
    "/dev/fd/1",
    "/dev/fd/2",
}
FILE_UNCHANGED_STUB = (
    "File unchanged since last read. The content from the earlier Read "
    "tool_result in this conversation is still current — refer to that "
    "instead of re-reading."
)
IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}
IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
NOTEBOOK_EXTENSION = ".ipynb"
PDF_EXTENSION = ".pdf"
PDF_MAX_PAGES_PER_READ = 20
PDF_AT_MENTION_INLINE_THRESHOLD = 10
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".tiff",
    ".tif",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".wmv",
    ".flv",
    ".m4v",
    ".mpeg",
    ".mpg",
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",
    ".m4a",
    ".wma",
    ".aiff",
    ".opus",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".xz",
    ".z",
    ".tgz",
    ".iso",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".o",
    ".a",
    ".obj",
    ".lib",
    ".app",
    ".msi",
    ".deb",
    ".rpm",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    ".pyc",
    ".pyo",
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".node",
    ".wasm",
    ".rlib",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".mdb",
    ".idx",
    ".psd",
    ".ai",
    ".eps",
    ".sketch",
    ".fig",
    ".xd",
    ".blend",
    ".3ds",
    ".max",
    ".swf",
    ".fla",
    ".lockb",
    ".dat",
    ".data",
}


def _resolve_path(
    ctx: ToolContext,
    value: str,
    *,
    require_absolute: bool = False,
) -> Path:
    path = Path(value)
    if require_absolute and not path.is_absolute():
        raise PermissionError(f"Path must be absolute: {value}")
    if not path.is_absolute():
        path = ctx.cwd / path
    return path.resolve()


class ReadFileArgs(BaseModel):
    file_path: str = Field(
        description="The absolute path to the file to read.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "The 0-based line offset to start reading from. Only provide "
            "this when the file is too large to read at once."
        ),
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description=(
            "The number of lines to read. Only provide this when the file is "
            "too large to read at once."
        ),
    )
    pages: str | None = Field(
        default=None,
        description=(
            'Page range for PDF files, for example "1-5", "3", or "10-20". '
            "Maximum 20 pages per request."
        ),
    )


class ReadFileTool:
    name = "Read"
    description = (
        "Reads a file from the local filesystem. You can access any file "
        "directly by using this tool.\n\n"
        "Usage:\n"
        "- The file_path parameter must be an absolute path, not a relative "
        "path\n"
        f"- By default, it reads up to {MAX_LINES_TO_READ} lines starting "
        "from the beginning of the file\n"
        "- You can optionally specify a line offset and limit, but it is "
        "recommended to read the whole file when possible\n"
        "- Results are returned using cat -n format, with line numbers "
        "starting at 1\n"
        "- This tool allows Claude Code to read images (eg PNG, JPG, etc)\n"
        "- This tool can read PDF files (.pdf). For large PDFs (more than 10 "
        "pages), you MUST provide the pages parameter to read specific page "
        "ranges. Maximum 20 pages per request.\n"
        "- This tool can read Jupyter notebooks (.ipynb files) and returns "
        "all cells with their outputs\n"
        "- This tool can only read files, not directories"
    )
    args_model = ReadFileArgs
    is_readonly = True

    def run(self, args: ReadFileArgs, ctx: ToolContext) -> ToolResult:
        path = _resolve_path(ctx, args.file_path, require_absolute=True)
        if is_blocked_device_path(path):
            return ToolResult(
                content=(
                    f"Cannot read '{args.file_path}': this device file "
                    "would block or produce infinite output."
                ),
                is_error=True,
            )
        suffix = path.suffix.lower()
        existing_state = ctx.read_state.get(path)
        if (
            suffix not in IMAGE_EXTENSIONS
            and suffix != PDF_EXTENSION
            and
            existing_state is not None
            and not existing_state.is_partial
            and existing_state.offset == args.offset
            and existing_state.limit == args.limit
            and existing_state.pages == args.pages
            and existing_state.timestamp_ns == path.stat().st_mtime_ns
        ):
            return ToolResult(content=FILE_UNCHANGED_STUB)
        if args.pages is not None:
            pdf_range = parse_pdf_page_range(args.pages)
            if pdf_range is None:
                return ToolResult(
                    content=(
                        f'Invalid pages parameter: "{args.pages}". Use '
                        'formats like "1-5", "3", or "10-20". Pages are '
                        "1-indexed."
                    ),
                    is_error=True,
                )
            range_size = pdf_range[1] - pdf_range[0] + 1
            if range_size > PDF_MAX_PAGES_PER_READ:
                return ToolResult(
                    content=(
                        f'Page range "{args.pages}" exceeds maximum of '
                        f"{PDF_MAX_PAGES_PER_READ} pages per request. "
                        "Please use a smaller range."
                    ),
                    is_error=True,
                )
        if suffix == PDF_EXTENSION:
            return read_pdf_tool_result(path, ctx, args)
        if suffix == NOTEBOOK_EXTENSION:
            return read_notebook_tool_result(path, ctx, args)
        if suffix in IMAGE_EXTENSIONS:
            raw = path.read_bytes()
            if not raw:
                return ToolResult(
                    content=f"Image file is empty: {path}",
                    is_error=True,
                )
            return ToolResult(
                content=[
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": IMAGE_MEDIA_TYPES[suffix],
                            "data": base64.b64encode(raw).decode("ascii"),
                        },
                    }
                ]
            )
        if has_binary_extension(path):
            return ToolResult(
                content=(
                    "This tool cannot read binary files. The file appears to "
                    f"be a binary {suffix} file. Please use appropriate tools "
                    "for binary file analysis."
                ),
                is_error=True,
            )
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        start = args.offset
        limit = args.limit or MAX_LINES_TO_READ
        selected = lines[start : start + limit]
        is_partial = start > 0 or start + limit < len(lines)
        ctx.read_state[path] = ReadState(
            timestamp_ns=path.stat().st_mtime_ns,
            is_partial=is_partial,
            offset=args.offset,
            limit=args.limit,
            pages=args.pages,
        )
        if not selected:
            return ToolResult(
                content=render_empty_or_short_read(
                    total_lines=len(lines),
                    offset=args.offset,
                )
            )
        return ToolResult(content=format_numbered_lines(selected, start + 1))


class GlobArgs(BaseModel):
    pattern: str = Field(description="The glob pattern to match.")
    path: str | None = Field(
        default=None,
        description="Optional directory to search within.",
    )


class GlobTool:
    name = "Glob"
    description = (
        "- Fast file pattern matching tool that works with any codebase size\n"
        '- Supports glob patterns like "**/*.js" or "src/**/*.ts"\n'
        "- Returns matching file paths sorted by modification time\n"
        "- Use this tool when you need to find files by name patterns"
    )
    args_model = GlobArgs
    is_readonly = True

    def run(self, args: GlobArgs, ctx: ToolContext) -> ToolResult:
        root = _resolve_path(ctx, args.path or ".")
        matches = [
            path_for_output(path, ctx.cwd)
            for path in sorted(
                (path for path in root.glob(args.pattern) if path.is_file()),
                key=lambda path: path.stat().st_mtime_ns,
                reverse=True,
            )
        ]
        if not matches:
            return ToolResult(content="No files found")
        truncated = len(matches) > DEFAULT_GLOB_LIMIT
        visible_matches = matches[:DEFAULT_GLOB_LIMIT]
        if truncated:
            visible_matches.append(
                "(Results are truncated. Consider using a more specific "
                "path or pattern.)"
            )
        return ToolResult(content="\n".join(visible_matches))


class GrepArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pattern: str
    path: str = Field(
        default=".",
        description="File or directory path to search within.",
    )
    glob: str | None = Field(
        default=None,
        description="Optional glob filter to limit matching files.",
    )
    output_mode: Literal["files_with_matches", "content", "count"] = Field(
        default="files_with_matches",
        description="One of files_with_matches, content, or count.",
    )
    before_context: int | None = Field(default=None, ge=0, alias="-B")
    after_context: int | None = Field(default=None, ge=0, alias="-A")
    context_shortcut: int | None = Field(default=None, ge=0, alias="-C")
    context: int | None = Field(default=None, ge=0)
    show_line_numbers: bool = Field(default=True, alias="-n")
    case_insensitive: bool = Field(default=False, alias="-i")
    file_type: str | None = Field(default=None, alias="type")
    head_limit: int | None = Field(default=None, ge=0)
    offset: int = Field(default=0, ge=0)
    multiline: bool = False


class GrepTool:
    name = "Grep"
    description = (
        "A powerful search tool built on ripgrep\n\n"
        "Usage:\n"
        "- ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as "
        "a Bash command. The Grep tool has been optimized for correct "
        "permissions and access.\n"
        '- Supports full regex syntax (e.g., "log.*Error", '
        '"function\\\\s+\\\\w+")\n'
        '- Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or '
        'type parameter (e.g., "js", "py", "rust")\n'
        '- Output modes: "content" shows matching lines, '
        '"files_with_matches" shows only file paths (default), "count" '
        "shows match counts\n"
        "- Pattern syntax uses ripgrep, not grep. Literal braces need "
        "escaping (use `interface\\{\\}` to find `interface{}` in Go code)\n"
        "- Multiline matching is disabled by default. Use multiline=true for "
        "cross-line patterns"
    )
    args_model = GrepArgs
    is_readonly = True

    def run(self, args: GrepArgs, ctx: ToolContext) -> ToolResult:
        root = _resolve_path(ctx, args.path)
        flags = re.IGNORECASE if args.case_insensitive else 0
        if args.multiline:
            flags |= re.DOTALL
        regex = re.compile(args.pattern, flags=flags)
        content_matches: list[str] = []
        file_match_counts: dict[str, int] = {}
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file():
                continue
            if args.glob is not None and not path.match(args.glob):
                continue
            if args.file_type is not None and path.suffix != f".{args.file_type}":
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = path_for_output(path, ctx.cwd)
            if args.multiline:
                matched_lines = collect_multiline_grep_matches(
                    content,
                    regex,
                    relative,
                    args,
                )
                if matched_lines:
                    content_matches.extend(matched_lines)
                    file_match_counts[relative] = count_multiline_matches(
                        content,
                        regex,
                    )
                continue
            matched_lines = collect_grep_content_matches(
                content,
                regex,
                relative,
                args,
            )
            if matched_lines:
                content_matches.extend(matched_lines)
                file_match_counts[relative] = count_matching_lines(content, regex)

        if args.output_mode == "content":
            lines = paginate_matches(content_matches, args.offset, args.head_limit)
            return ToolResult(content="\n".join(lines) or "No matches found")
        if args.output_mode == "count":
            count_lines = [
                f"{path}:{count}"
                for path, count in sorted(file_match_counts.items())
            ]
            lines = paginate_matches(count_lines, args.offset, args.head_limit)
            return ToolResult(content="\n".join(lines) or "No matches found")

        files = sorted(file_match_counts)
        files = paginate_matches(files, args.offset, args.head_limit)
        if not files:
            return ToolResult(content="No files found")
        return ToolResult(
            content=f"Found {len(files)} file(s)\n" + "\n".join(files)
        )


class WriteFileArgs(BaseModel):
    file_path: str = Field(
        description="The absolute path to the file to write.",
    )
    content: str = Field(description="The full file contents to write.")


class WriteFileTool:
    name = "Write"
    description = (
        "Writes a file to the local filesystem.\n\n"
        "Usage:\n"
        "- This tool will overwrite the existing file if there is one at the "
        "provided path.\n"
        "- If this is an existing file, you MUST use the Read tool first to "
        "read the file's contents. This tool will fail if you did not read "
        "the file first.\n"
        "- Prefer Edit for modifying existing files. Only use this tool to "
        "create new files or for complete rewrites.\n"
        "- NEVER create documentation files (*.md) or README files unless "
        "explicitly requested by the User.\n"
        "- Only use emojis if the user explicitly requests it. Avoid writing "
        "emojis to files unless asked."
    )
    args_model = WriteFileArgs
    is_readonly = False

    def run(self, args: WriteFileArgs, ctx: ToolContext) -> ToolResult:
        try:
            path = _resolve_path(ctx, args.file_path, require_absolute=True)
            error = require_fresh_read(
                ctx,
                path,
                tool_name=self.name,
                allow_missing=True,
            )
            if error is not None:
                return error
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.content, encoding="utf-8")
            ctx.read_state[path] = ReadState(
                timestamp_ns=path.stat().st_mtime_ns,
                is_partial=False,
                offset=None,
                limit=None,
                pages=None,
            )
        except Exception as exc:
            return ToolResult(
                content=f"Failed to write {args.file_path}: {exc}",
                is_error=True,
            )
        return ToolResult(
            content=f"Wrote {len(args.content.splitlines())} lines to {path}"
        )


class EditFileArgs(BaseModel):
    file_path: str = Field(
        description="The absolute path to the file to edit.",
    )
    old_string: str = Field(
        description="The exact text to replace.",
    )
    new_string: str = Field(
        description="The replacement text.",
    )
    replace_all: bool = Field(
        default=False,
        description="Replace every occurrence of old_string in the file.",
    )


class EditFileTool:
    name = "Edit"
    description = (
        "Performs exact string replacements in files.\n\n"
        "Usage:\n"
        "- You must use your `Read` tool at least once in the conversation "
        "before editing. This tool will error if you attempt an edit "
        "without reading the file.\n"
        "- When editing text from Read tool output, ensure you preserve the "
        "exact indentation (tabs/spaces) as it appears AFTER the line number "
        "prefix. The line number prefix format is: line number + tab. "
        "Everything after that is the actual file content to match. Never "
        "include any part of the line number prefix in old_string or "
        "new_string.\n"
        "- ALWAYS prefer editing existing files in the codebase. NEVER write "
        "new files unless explicitly required.\n"
        "- Only use emojis if the user explicitly requests it. Avoid adding "
        "emojis to files unless asked.\n"
        "- The edit will FAIL if `old_string` is not unique in the file. "
        "Either provide a larger string with more surrounding context or use "
        "`replace_all`.\n"
        "- Use `replace_all` for replacing and renaming strings across the file."
    )
    args_model = EditFileArgs
    is_readonly = False

    def run(self, args: EditFileArgs, ctx: ToolContext) -> ToolResult:
        try:
            path = _resolve_path(ctx, args.file_path, require_absolute=True)
            error = require_fresh_read(
                ctx,
                path,
                tool_name=self.name,
                allow_missing=args.old_string == "",
            )
            if error is not None:
                return error
            content = path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception as exc:
            return ToolResult(
                content=f"Failed to read {args.file_path}: {exc}",
                is_error=True,
            )
        if path.suffix.lower() == NOTEBOOK_EXTENSION and path.exists():
            return ToolResult(
                content=(
                    "File is a Jupyter Notebook. Use the NotebookEdit "
                    "tool to edit this file."
                ),
                is_error=True,
            )
        if args.old_string == args.new_string:
            return ToolResult(
                content=(
                    "No changes to make: old_string and new_string are "
                    "exactly the same."
                ),
                is_error=True,
            )
        if not path.exists() and args.old_string == "":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args.new_string, encoding="utf-8")
            ctx.read_state[path] = ReadState(
                timestamp_ns=path.stat().st_mtime_ns,
                is_partial=False,
                offset=None,
                limit=None,
                pages=None,
            )
            return ToolResult(content=f"Edited {path}")
        if args.old_string not in content:
            hint = closest_lines_hint(content, args.old_string)
            return ToolResult(
                content=(
                    f"Could not find target text in {path}.\n"
                    f"Target preview: {truncate_preview(args.old_string)}\n"
                    f"{hint}"
                ),
                is_error=True,
            )
        occurrences = content.count(args.old_string)
        if occurrences > 1 and not args.replace_all:
            return ToolResult(
                content=(
                    f"old_string is not unique in {path} ({occurrences} matches). "
                    "Provide more context or set replace_all=true."
                ),
                is_error=True,
            )
        count = occurrences if args.replace_all else 1
        updated = content.replace(args.old_string, args.new_string, count)
        try:
            path.write_text(updated, encoding="utf-8")
            ctx.read_state[path] = ReadState(
                timestamp_ns=path.stat().st_mtime_ns,
                is_partial=False,
                offset=None,
                limit=None,
                pages=None,
            )
        except Exception as exc:
            return ToolResult(
                content=f"Failed to write {args.file_path}: {exc}",
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


def format_numbered_lines(lines: list[str], start_line: int) -> str:
    return "\n".join(
        f"{line_number}\t{line}"
        for line_number, line in enumerate(lines, start=start_line)
    )


def render_empty_or_short_read(total_lines: int, offset: int) -> str:
    if total_lines == 0:
        return (
            "<system-reminder>Warning: the file exists but the contents are "
            "empty.</system-reminder>"
        )
    return (
        "<system-reminder>Warning: the file exists but is shorter than the "
        f"provided offset ({offset}). The file has {total_lines} lines."
        "</system-reminder>"
    )


def path_for_output(path: Path, cwd: Path) -> str:
    try:
        return str(path.relative_to(cwd.resolve()))
    except ValueError:
        return str(path)


def has_binary_extension(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def is_blocked_device_path(path: Path) -> bool:
    normalized = path.as_posix()
    if normalized in BLOCKED_DEVICE_PATHS:
        return True
    if normalized.startswith("/proc/") and (
        normalized.endswith("/fd/0")
        or normalized.endswith("/fd/1")
        or normalized.endswith("/fd/2")
    ):
        return True
    return False


def parse_pdf_page_range(pages: str) -> tuple[int, int] | None:
    trimmed = pages.strip()
    if not trimmed:
        return None
    if trimmed.endswith("-"):
        first = trimmed[:-1]
        if not first.isdigit() or int(first) < 1:
            return None
        return int(first), int(first) + PDF_MAX_PAGES_PER_READ
    if "-" not in trimmed:
        if not trimmed.isdigit() or int(trimmed) < 1:
            return None
        page = int(trimmed)
        return page, page
    first, last = trimmed.split("-", 1)
    if (
        not first.isdigit()
        or not last.isdigit()
        or int(first) < 1
        or int(last) < int(first)
    ):
        return None
    return int(first), int(last)


def read_pdf_tool_result(
    path: Path,
    ctx: ToolContext,
    args: ReadFileArgs,
) -> ToolResult:
    try:
        import fitz
    except ImportError:
        return ToolResult(
            content=(
                "PDF reading requires PyMuPDF (`fitz`). Install `pymupdf` "
                "to enable PDF support."
            ),
            is_error=True,
        )

    try:
        with fitz.open(path) as document:
            page_count = document.page_count
            if args.pages is None and page_count > PDF_AT_MENTION_INLINE_THRESHOLD:
                return ToolResult(
                    content=(
                        f"This PDF has {page_count} pages, which is too many "
                        'to read at once. Use the pages parameter to read '
                        'specific page ranges (e.g., pages: "1-5"). Maximum '
                        f"{PDF_MAX_PAGES_PER_READ} pages per request."
                    ),
                    is_error=True,
                )
            first_page, last_page = (
                parse_pdf_page_range(args.pages)
                if args.pages is not None
                else (1, page_count)
            )
            first_index = max(0, first_page - 1)
            last_index = min(page_count, last_page) - 1
            rendered_pages: list[str] = []
            for page_index in range(first_index, last_index + 1):
                page = document.load_page(page_index)
                text = page.get_text("text").rstrip()
                rendered_page = (
                    f"Page {page_index + 1}\n{text}"
                    if text
                    else f"Page {page_index + 1}"
                )
                rendered_pages.append(rendered_page)
    except Exception as exc:
        return ToolResult(
            content=f"Failed to read PDF {path}: {exc}",
            is_error=True,
        )

    content = "\n\n".join(rendered_pages).strip()
    if not content:
        return ToolResult(
            content=f"PDF file is empty: {path}",
            is_error=True,
        )
    return ToolResult(content=content)


def read_notebook_tool_result(
    path: Path,
    ctx: ToolContext,
    args: ReadFileArgs,
) -> ToolResult:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        return ToolResult(
            content=f"Notebook is missing a valid cells array: {path}",
            is_error=True,
        )

    metadata = notebook.get("metadata", {})
    language_info = metadata.get("language_info", {})
    language = (
        language_info.get("name")
        if isinstance(language_info, dict)
        else None
    )
    blocks = merge_adjacent_text_blocks(
        [
            block
            for index, cell in enumerate(cells)
            for block in notebook_cell_to_blocks(
                cell,
                index=index,
                language=language if isinstance(language, str) else "python",
            )
        ]
    )
    ctx.read_state[path] = ReadState(
        timestamp_ns=path.stat().st_mtime_ns,
        is_partial=False,
        offset=args.offset,
        limit=args.limit,
        pages=args.pages,
    )
    return ToolResult(content=blocks)


def notebook_cell_to_blocks(
    cell: object,
    *,
    index: int,
    language: str,
) -> list[dict[str, object]]:
    if not isinstance(cell, dict):
        return []

    cell_type = cell.get("cell_type")
    source = normalize_notebook_text(cell.get("source"))
    cell_id = cell.get("id")
    if not isinstance(cell_id, str) or not cell_id:
        cell_id = f"cell-{index}"

    metadata: list[str] = []
    if cell_type != "code" and isinstance(cell_type, str):
        metadata.append(f"<cell_type>{cell_type}</cell_type>")
    if cell_type == "code" and language != "python":
        metadata.append(f"<language>{language}</language>")

    blocks: list[dict[str, object]] = [
        {
            "type": "text",
            "text": (
                f'<cell id="{cell_id}">'
                f"{''.join(metadata)}{source}"
                f'</cell id="{cell_id}">'
            ),
        }
    ]
    for output in notebook_outputs_to_blocks(cell.get("outputs")):
        blocks.append(output)
    return blocks


def notebook_outputs_to_blocks(outputs: object) -> list[dict[str, object]]:
    if not isinstance(outputs, list):
        return []

    blocks: list[dict[str, object]] = []
    for output in outputs:
        if not isinstance(output, dict):
            continue
        output_type = output.get("output_type")
        if output_type == "stream":
            text = normalize_notebook_text(output.get("text"))
            if text:
                blocks.append({"type": "text", "text": f"\n{text}"})
            continue
        if output_type in {"execute_result", "display_data"}:
            data = output.get("data")
            if not isinstance(data, dict):
                continue
            text = normalize_notebook_text(data.get("text/plain"))
            if text:
                blocks.append({"type": "text", "text": f"\n{text}"})
            image_block = notebook_output_image_block(data)
            if image_block is not None:
                blocks.append(image_block)
            continue
        if output_type == "error":
            ename = output.get("ename")
            evalue = output.get("evalue")
            traceback = output.get("traceback")
            traceback_text = normalize_notebook_text(traceback)
            parts = [
                part
                for part in [
                    f"{ename}: {evalue}"
                    if isinstance(ename, str) and isinstance(evalue, str)
                    else None,
                    traceback_text or None,
                ]
                if part
            ]
            if parts:
                blocks.append({"type": "text", "text": "\n" + "\n".join(parts)})
    return blocks


def notebook_output_image_block(
    data: dict[object, object],
) -> dict[str, object] | None:
    for key, media_type in (
        ("image/png", "image/png"),
        ("image/jpeg", "image/jpeg"),
    ):
        value = data.get(key)
        if isinstance(value, str):
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": "".join(value.split()),
                },
            }
    return None


def normalize_notebook_text(value: object) -> str:
    if isinstance(value, list):
        parts = [part for part in value if isinstance(part, str)]
        return "".join(parts)
    if isinstance(value, str):
        return value
    return ""


def merge_adjacent_text_blocks(
    blocks: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    for block in blocks:
        if (
            merged
            and merged[-1].get("type") == "text"
            and block.get("type") == "text"
            and isinstance(merged[-1].get("text"), str)
            and isinstance(block.get("text"), str)
        ):
            merged[-1]["text"] += "\n" + block["text"]
            continue
        merged.append(block)
    return merged


def paginate_matches(
    items: list[str],
    offset: int,
    head_limit: int | None,
) -> list[str]:
    sliced = items[offset:]
    if head_limit == 0:
        return sliced
    effective_limit = (
        DEFAULT_GREP_HEAD_LIMIT if head_limit is None else head_limit
    )
    return sliced[:effective_limit]


def collect_grep_content_matches(
    content: str,
    regex: re.Pattern[str],
    display_path: str,
    args: GrepArgs,
) -> list[str]:
    lines = content.splitlines()
    matching_indexes = [
        index
        for index, line in enumerate(lines)
        if regex.search(line)
    ]
    if not matching_indexes:
        return []

    included_indexes = sorted(
        expand_context_indexes(matching_indexes, len(lines), args)
    )
    rendered: list[str] = []
    for index in included_indexes:
        line_number = index + 1
        line = lines[index]
        if args.show_line_numbers:
            rendered.append(f"{display_path}:{line_number}: {line}")
        else:
            rendered.append(f"{display_path}: {line}")
    return rendered


def expand_context_indexes(
    matching_indexes: list[int],
    line_count: int,
    args: GrepArgs,
) -> set[int]:
    context = resolved_grep_context(args)
    before = context if context is not None else (args.before_context or 0)
    after = context if context is not None else (args.after_context or 0)
    included: set[int] = set()
    for index in matching_indexes:
        start = max(0, index - before)
        end = min(line_count - 1, index + after)
        included.update(range(start, end + 1))
    return included


def resolved_grep_context(args: GrepArgs) -> int | None:
    if args.context is not None:
        return args.context
    if args.context_shortcut is not None:
        return args.context_shortcut
    return None


def count_matching_lines(content: str, regex: re.Pattern[str]) -> int:
    return sum(1 for line in content.splitlines() if regex.search(line))


def collect_multiline_grep_matches(
    content: str,
    regex: re.Pattern[str],
    display_path: str,
    args: GrepArgs,
) -> list[str]:
    line_ranges = multiline_match_line_ranges(content, regex)
    if not line_ranges:
        return []

    lines = content.splitlines()
    matching_indexes: list[int] = []
    for start_line, end_line in line_ranges:
        matching_indexes.extend(range(start_line - 1, end_line))

    included_indexes = sorted(
        expand_context_indexes(sorted(set(matching_indexes)), len(lines), args)
    )
    rendered: list[str] = []
    for index in included_indexes:
        line_number = index + 1
        line = lines[index]
        if args.show_line_numbers:
            rendered.append(f"{display_path}:{line_number}: {line}")
        else:
            rendered.append(f"{display_path}: {line}")
    return rendered


def multiline_match_line_ranges(
    content: str,
    regex: re.Pattern[str],
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in regex.finditer(content):
        start_line = content.count("\n", 0, match.start()) + 1
        end_index = max(match.start(), match.end() - 1)
        end_line = content.count("\n", 0, end_index) + 1
        ranges.append((start_line, end_line))
    return ranges


def count_multiline_matches(content: str, regex: re.Pattern[str]) -> int:
    return sum(1 for _ in regex.finditer(content))


def require_fresh_read(
    ctx: ToolContext,
    path: Path,
    *,
    tool_name: str,
    allow_missing: bool,
) -> ToolResult | None:
    if not path.exists():
        if allow_missing:
            return None
        return ToolResult(content=f"File does not exist: {path}", is_error=True)

    state = ctx.read_state.get(path)
    if state is None or state.is_partial:
        return ToolResult(
            content=(
                "File has not been read yet. "
                "Read it first before writing to it."
            ),
            is_error=True,
        )
    if (
        state.timestamp_ns is not None
        and path.stat().st_mtime_ns > state.timestamp_ns
    ):
        return ToolResult(
            content=(
                "File has been modified since read, either by the user or by a "
                "linter. Read it again before attempting to write it."
            ),
            is_error=True,
        )
    return None
