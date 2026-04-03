# nano-claude-code-py

A minimal terminal coding agent in Python with tool use, shell execution, and file editing.

`nano-claude-code-py` is a small, focused project that keeps only the core
agent loop:

`prompt -> model -> tool use -> local execution -> tool result -> final response`

It is not a full reimplementation of Claude Code. The goal is to build a
minimal, understandable, hackable Python codebase that implements a small,
source-aligned subset of Claude Code's terminal agent behavior for local file
work, shell execution, and multi-turn sessions.

## Goals

- Build a terminal-native coding agent in Python.
- Keep the runtime small enough to understand in a single sitting.
- Prioritize the core loop over advanced product features.
- Make the project easy to extend with more tools and providers later.

## MVP Scope

The first usable version is intentionally narrow.

### Core Features

- Interactive REPL for multi-turn conversations
- One-shot `run` mode for scripts and testing
- Anthropic Messages API integration
- Streaming text output
- Tool registry and tool execution loop
- File tools:
  - `Read`
  - `Glob`
  - `Grep`
  - `TodoWrite`
  - `Write`
  - `Edit`
  - `NotebookEdit`
  - `Bash`
- `Read` supports text files, common images, Jupyter notebooks, and PDFs
- `Read` supports PDFs with a source-aligned `pages` parameter and a 10-page inline limit
- `Edit` and `Write` require a prior `Read` on existing files, matching claude-code behavior
- `Edit` rejects `.ipynb` files, matching claude-code's `NotebookEdit` split
- `NotebookEdit` supports `replace`, `insert`, and `delete` cell edits after a prior `Read`
- `TodoWrite` supports source-aligned session todo tracking with `pending`, `in_progress`, and `completed` states
- `Bash` supports readonly classification, background execution, timeout handling, and source-aligned permission summaries for the implemented subset
- `Bash` currently executes commands locally without sandboxing
- Local transcript/session state
- Resume the latest local transcript
- Export transcripts to plaintext
- Minimal permission modes:
  - `default`
  - `acceptEdits`
  - `bypassPermissions`
  - `dontAsk`
  - `plan`

### Non-Goals

The following are explicitly out of scope for the nano version:

- MCP
- Plugin system
- Multi-agent orchestration
- Remote execution
- IDE integration
- Voice mode
- Rich TUI parity with the TypeScript client
- Advanced context compaction and recovery systems

## Project Layout

```text
src/nano_claude_code_py/
  cli.py              # Typer command-line entrypoints
  repl.py             # Interactive chat loop
  config.py           # Environment-backed settings
  models.py           # Shared message and tool models
  session.py          # Local transcript handling
  llm/
    client.py         # Model client interface
    tool_loop.py      # Core tool-use loop
  tools/
    base.py           # Tool protocol and context
    registry.py       # Tool registry
    file_tools.py     # Read/Glob/Grep/Write/Edit tools
    notebook_tools.py # NotebookEdit tool
    todo_tools.py     # TodoWrite session task tracking
    shell_tools.py    # Bash execution tool
tests/
  test_registry.py
  test_file_tools.py
  test_notebook_tools.py
  test_todo_tools.py
  test_shell_tools.py
  test_permissions.py
  test_tool_loop.py
  test_session.py
  test_repl.py
  test_cli.py
```

## Roadmap

### v0.1

- Project skeleton
- CLI entrypoint
- File and shell tools
- Local transcript model
- Anthropic client integration
- End-to-end tool loop
- Tests and CI

### v0.2

- Streaming responses
- REPL command handling
- Resume the latest transcript

### Current Focus

- Finish source-alignment cleanup for the implemented nano subset
- Keep tool descriptions, prompts, permission summaries, and common error
  messages aligned with Claude Code where the feature exists in this repo
- Avoid adding out-of-scope product features before the implemented subset is
  behaviorally stable

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
export ANTHROPIC_API_KEY=your_key_here
nano-claude --help
```

Run the REPL:

```bash
nano-claude
```

Resume the latest saved transcript:

```bash
nano-claude --resume
```

List saved transcripts:

```bash
nano-claude sessions
```

Export the latest transcript to plaintext:

```bash
nano-claude export
```

Export a specific transcript to a custom file:

```bash
nano-claude export --index 2 --output exports/session-2.txt
```

Inside the REPL:

```text
/help
/tools
/sessions
/session
/history 20
/save
/export
/export custom.txt
/clear
/exit
```

Run a one-shot prompt:

```bash
nano-claude -p "summarize this repository"
```

## Development

Run lint and tests:

```bash
ruff check .
pytest
```

## License

MIT
