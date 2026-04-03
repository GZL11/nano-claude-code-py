import base64
import json
import os

from nano_claude_code_py.tools.base import ToolContext
from nano_claude_code_py.tools.file_tools import (
    FILE_UNCHANGED_STUB,
    EditFileArgs,
    EditFileTool,
    GlobArgs,
    GlobTool,
    GrepArgs,
    GrepTool,
    ReadFileArgs,
    ReadFileTool,
    WriteFileArgs,
    WriteFileTool,
    closest_lines_hint,
)


def test_write_and_read_file(tmp_path):
    ctx = ToolContext(cwd=tmp_path)
    path = tmp_path / "demo.txt"
    WriteFileTool().run(WriteFileArgs(file_path=str(path), content="hello"), ctx)
    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert result.content == "1\thello"


def test_read_supports_absolute_path_outside_cwd(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-read"
    outside_dir.mkdir()
    path = outside_dir / "demo.txt"
    path.write_text("outside\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert result.content == "1\toutside"


def test_read_returns_unchanged_stub_for_same_range_without_modification(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    first = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)
    second = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert first.content == "1\talpha\n2\tbeta"
    assert second.content == FILE_UNCHANGED_STUB


def test_read_returns_content_again_after_file_changes(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("alpha\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)
    original_mtime = path.stat().st_mtime_ns
    path.write_text("beta\n", encoding="utf-8")
    os.utime(path, ns=(original_mtime + 1_000_000, original_mtime + 1_000_000))

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert result.content == "1\tbeta"


def test_read_returns_image_blocks_for_supported_images(tmp_path):
    path = tmp_path / "pixel.png"
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNg"
            "YAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
    )
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert isinstance(result.content, list)
    assert result.content[0]["type"] == "image"
    source = result.content[0]["source"]
    assert source["type"] == "base64"
    assert source["media_type"] == "image/png"
    assert isinstance(source["data"], str)


def test_read_does_not_return_unchanged_stub_for_repeated_image_reads(tmp_path):
    path = tmp_path / "pixel.png"
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNg"
            "YAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
    )
    ctx = ToolContext(cwd=tmp_path)

    first = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)
    second = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert isinstance(first.content, list)
    assert isinstance(second.content, list)
    assert second.content != FILE_UNCHANGED_STUB
    assert second.content[0]["type"] == "image"


def test_read_rejects_binary_files_by_extension(tmp_path):
    path = tmp_path / "archive.bin"
    path.write_bytes(b"\x00\x01\x02")
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert result.is_error
    assert "cannot read binary files" in result.content


def test_read_rejects_blocked_device_paths(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path="/dev/zero"), ctx)

    assert result.is_error
    assert "would block or produce infinite output" in result.content


def test_read_returns_notebook_content_blocks(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        json.dumps(
            {
                "metadata": {"language_info": {"name": "python"}},
                "cells": [
                    {
                        "cell_type": "markdown",
                        "source": ["# Title\n"],
                    },
                    {
                        "cell_type": "code",
                        "source": ['print("hello")\n'],
                        "outputs": [
                            {
                                "output_type": "stream",
                                "text": ["hello\n"],
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert isinstance(result.content, list)
    assert result.content[0]["type"] == "text"
    text = result.content[0]["text"]
    assert (
        '<cell id="cell-0"><cell_type>markdown</cell_type># Title\n'
        '</cell id="cell-0">'
    ) in text
    assert '<cell id="cell-1">print("hello")\n</cell id="cell-1">' in text
    assert "hello\n" in text


def test_read_extracts_pdf_text_for_small_documents(tmp_path):
    fitz = __import__("fitz")
    path = tmp_path / "demo.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "hello pdf")
    document.save(path)
    document.close()
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert result.content == "Page 1\nhello pdf"


def test_read_rejects_large_pdf_without_pages_parameter(tmp_path):
    fitz = __import__("fitz")
    path = tmp_path / "demo.pdf"
    document = fitz.open()
    for index in range(11):
        page = document.new_page()
        page.insert_text((72, 72), f"page {index + 1}")
    document.save(path)
    document.close()
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert result.is_error
    assert "too many to read at once" in result.content
    assert 'pages: "1-5"' in result.content


def test_read_supports_pdf_page_ranges(tmp_path):
    fitz = __import__("fitz")
    path = tmp_path / "demo.pdf"
    document = fitz.open()
    for index in range(3):
        page = document.new_page()
        page.insert_text((72, 72), f"page {index + 1}")
    document.save(path)
    document.close()
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(
        ReadFileArgs(file_path=str(path), pages="2-3"),
        ctx,
    )

    assert result.content == "Page 2\npage 2\n\nPage 3\npage 3"


def test_read_does_not_return_unchanged_stub_for_repeated_pdf_reads(tmp_path):
    fitz = __import__("fitz")
    path = tmp_path / "demo.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "hello pdf")
    document.save(path)
    document.close()
    ctx = ToolContext(cwd=tmp_path)

    first = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)
    second = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert first.content == "Page 1\nhello pdf"
    assert second.content == "Page 1\nhello pdf"


def test_read_rejects_invalid_pdf_pages_parameter(tmp_path):
    fitz = __import__("fitz")
    path = tmp_path / "demo.pdf"
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(
        ReadFileArgs(file_path=str(path), pages="0-2"),
        ctx,
    )

    assert result.is_error
    assert 'Invalid pages parameter: "0-2"' in result.content


def test_read_does_not_reuse_pdf_stub_for_different_page_ranges(tmp_path):
    fitz = __import__("fitz")
    path = tmp_path / "demo.pdf"
    document = fitz.open()
    for index in range(3):
        page = document.new_page()
        page.insert_text((72, 72), f"page {index + 1}")
    document.save(path)
    document.close()
    ctx = ToolContext(cwd=tmp_path)

    first = ReadFileTool().run(ReadFileArgs(file_path=str(path), pages="1"), ctx)
    second = ReadFileTool().run(ReadFileArgs(file_path=str(path), pages="2"), ctx)

    assert first.content == "Page 1\npage 1"
    assert second.content == "Page 2\npage 2"


def test_edit_file(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello world", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="world",
            new_string="agent",
        ),
        ctx,
    )

    assert not result.is_error
    assert path.read_text(encoding="utf-8") == "hello agent"


def test_edit_rejects_jupyter_notebooks(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        json.dumps({"metadata": {}, "cells": []}),
        encoding="utf-8",
    )
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="[]",
            new_string="[1]",
        ),
        ctx,
    )

    assert result.is_error
    assert "NotebookEdit" in result.content


def test_edit_supports_absolute_path_outside_cwd_after_read(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-edit"
    outside_dir.mkdir()
    path = outside_dir / "demo.txt"
    path.write_text("hello world", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="world",
            new_string="agent",
        ),
        ctx,
    )

    assert not result.is_error
    assert path.read_text(encoding="utf-8") == "hello agent"


def test_glob_lists_matching_files(tmp_path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GlobTool().run(GlobArgs(path=".", pattern="*.py"), ctx)

    assert result.content == "a.py"


def test_glob_returns_no_files_message(tmp_path):
    ctx = ToolContext(cwd=tmp_path)

    result = GlobTool().run(GlobArgs(path=".", pattern="*.py"), ctx)

    assert result.content == "No files found"


def test_glob_uses_absolute_output_for_matches_outside_cwd(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-glob"
    outside_dir.mkdir()
    path = outside_dir / "a.py"
    path.write_text("", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GlobTool().run(GlobArgs(path=str(outside_dir), pattern="*.py"), ctx)

    assert result.content == str(path)


def test_grep_finds_matching_lines(tmp_path):
    (tmp_path / "demo.py").write_text("alpha\nbeta\nalpha beta\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(pattern="alpha", path=".", output_mode="content"),
        ctx,
    )

    assert "demo.py:1: alpha" in result.content
    assert "demo.py:3: alpha beta" in result.content


def test_grep_uses_absolute_output_for_matches_outside_cwd(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-grep"
    outside_dir.mkdir()
    path = outside_dir / "demo.py"
    path.write_text("alpha\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(pattern="alpha", path=str(outside_dir), output_mode="content"),
        ctx,
    )

    assert result.content == f"{path}:1: alpha"


def test_grep_files_with_matches_includes_summary(tmp_path):
    (tmp_path / "demo.py").write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(GrepArgs(pattern="alpha", path="."), ctx)

    assert result.content.startswith("Found 1 file(s)\n")
    assert "demo.py" in result.content


def test_read_supports_0_based_offset_and_limit(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(
        ReadFileArgs(file_path=str(path), offset=1, limit=1),
        ctx,
    )

    assert result.content == "2\tbeta"


def test_read_warns_for_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    assert "file exists but the contents are empty" in result.content


def test_read_warns_when_offset_is_past_end_of_file(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = ReadFileTool().run(
        ReadFileArgs(file_path=str(path), offset=10),
        ctx,
    )

    assert "shorter than the provided offset (10)" in result.content


def test_grep_supports_case_insensitive_type_and_pagination(tmp_path):
    (tmp_path / "a.py").write_text("Alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("alpha\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(
            pattern="alpha",
            path=".",
            output_mode="content",
            **{"-i": True, "type": "py", "head_limit": 1, "offset": 0},
        ),
        ctx,
    )

    assert result.content == "a.py:1: Alpha"


def test_grep_supports_context_shortcuts_and_hides_line_numbers(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text("one\nalpha\ntwo\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(
            pattern="alpha",
            path=".",
            output_mode="content",
            **{"-C": 1, "-n": False},
        ),
        ctx,
    )

    assert result.content == "demo.py: one\ndemo.py: alpha\ndemo.py: two"


def test_grep_supports_multiline_matching(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text("alpha\nmid\nomega\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(
            pattern="alpha\\nmid\\nomega",
            path=".",
            output_mode="content",
            multiline=True,
        ),
        ctx,
    )

    assert result.content == "demo.py:1: alpha\ndemo.py:2: mid\ndemo.py:3: omega"


def test_grep_supports_searching_a_single_file_path(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text("alpha\nbeta\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(pattern="alpha", path=str(path), output_mode="content"),
        ctx,
    )

    assert result.content == "demo.py:1: alpha"


def test_grep_returns_no_matches_message_for_content_mode(tmp_path):
    (tmp_path / "demo.py").write_text("alpha\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = GrepTool().run(
        GrepArgs(pattern="beta", path=".", output_mode="content"),
        ctx,
    )

    assert result.content == "No matches found"


def test_edit_file_reports_helpful_hint_when_text_is_missing(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello world\nhello agent\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="hello user",
            new_string="x",
        ),
        ctx,
    )

    assert result.is_error
    assert "Could not find target text" in result.content
    assert "Possible nearby lines" in result.content


def test_closest_lines_hint_returns_fallback_for_no_matches():
    hint = closest_lines_hint("alpha\nbeta\n", "gamma")
    assert "No similar nearby lines were found." in hint


def test_write_requires_prior_read_for_existing_file(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = WriteFileTool().run(
        WriteFileArgs(file_path=str(path), content="updated"),
        ctx,
    )

    assert result.is_error
    assert "Read it first before writing to it." in result.content


def test_write_supports_absolute_new_file_outside_cwd(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-write"
    outside_dir.mkdir()
    path = outside_dir / "new.txt"
    ctx = ToolContext(cwd=tmp_path)

    result = WriteFileTool().run(
        WriteFileArgs(file_path=str(path), content="created"),
        ctx,
    )

    assert not result.is_error
    assert path.read_text(encoding="utf-8") == "created"


def test_edit_requires_prior_read_for_existing_file(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="hello",
            new_string="updated",
        ),
        ctx,
    )

    assert result.is_error
    assert "Read it first before writing to it." in result.content


def test_edit_rejects_notebooks_with_notebookedit_tool_hint(tmp_path):
    path = tmp_path / "demo.ipynb"
    path.write_text('{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}\n')
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="x",
            new_string="y",
        ),
        ctx,
    )

    assert result.is_error
    assert "Use the NotebookEdit tool to edit this file." in result.content


def test_edit_uses_source_aligned_modified_since_read_message(tmp_path):
    path = tmp_path / "demo.txt"
    path.write_text("hello", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)
    path.write_text("updated externally", encoding="utf-8")
    read_timestamp = ctx.read_state[path].timestamp_ns
    assert read_timestamp is not None
    os.utime(path, ns=(read_timestamp + 1, read_timestamp + 1))

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="hello",
            new_string="updated",
        ),
        ctx,
    )

    assert result.is_error
    assert "Read it again before attempting to write it." in result.content


def test_edit_replace_all_updates_every_occurrence(tmp_path):
    path = tmp_path / "demo.py"
    path.write_text("alpha beta\nalpha gamma\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadFileTool().run(ReadFileArgs(file_path=str(path)), ctx)

    result = EditFileTool().run(
        EditFileArgs(
            file_path=str(path),
            old_string="alpha",
            new_string="omega",
            replace_all=True,
        ),
        ctx,
    )

    assert not result.is_error
    assert path.read_text(encoding="utf-8") == "omega beta\nomega gamma\n"
