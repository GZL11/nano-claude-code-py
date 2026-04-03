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

## What This Repo Reproduces

This repository does not aim to reproduce all of Claude Code. It reproduces a
small, source-aligned `nano` subset of the terminal agent workflow:

- Interactive chat loop with local conversation state
- One-shot execution mode
- Anthropic Messages API integration
- Streaming assistant output
- Tool calling and tool-result turn loop
- Local permissions with Claude Code-style nano modes
- Claude Code-style core file and shell tools for the implemented subset
- Local transcript persistence, resume, listing, and plaintext export

For the implemented subset, the project explicitly aligns these areas with
Claude Code source as closely as practical:

- Tool names
- Tool descriptions
- Input schema fields
- Core permission mode names
- Common tool error flows
- Read-before-write / Read-before-edit behavior
- `Edit` versus `NotebookEdit` split
- `TodoWrite` task state model
- `Bash` readonly classification for the supported nano subset

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
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --no-build-isolation -e ".[dev]"
cp .env.example .env
export ANTHROPIC_API_KEY=your_key_here
nano-claude --help
```

The `--no-build-isolation` flag avoids unnecessary build-backend downloads in
restricted or offline environments. The `--system-site-packages` venv option
lets the editable install reuse already-available base packages when needed.

Start interactive mode:

```bash
nano-claude
```

Run a one-shot prompt:

```bash
nano-claude -p "summarize this repository"
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

## Configuration

Configuration is environment-backed. The main settings are:

- `ANTHROPIC_API_KEY`: required for model calls
- `NANO_CLAUDE_LANGUAGE`: response language for the system prompt
- `model`: default model name in code/config
- `permission_mode`: one of `default`, `acceptEdits`, `bypassPermissions`, `dontAsk`, `plan`
- `session_dir`: local transcript directory

You can configure language at runtime or through environment variables.

English:

```bash
export NANO_CLAUDE_LANGUAGE=english
nano-claude
```

Chinese:

```bash
export NANO_CLAUDE_LANGUAGE=zh
nano-claude
```

Japanese:

```bash
export NANO_CLAUDE_LANGUAGE=ja
nano-claude
```

Korean:

```bash
export NANO_CLAUDE_LANGUAGE=ko
nano-claude
```

You can also switch language per invocation:

```bash
nano-claude --language zh
nano-claude -p "请用中文总结这个仓库" --language zh
nano-claude --language ja
nano-claude --language ko
```

Supported language values include `english`, `zh`, `ja`, and `ko`.

When Chinese, Japanese, or Korean mode is enabled, the agent is instructed to
respond in that language while keeping code, commands, paths, and API
identifiers in their original form.

## Implemented Tools

The current `nano` subset includes:

- `Read`
  - Text files
  - Images
  - Jupyter notebooks
  - PDFs with page-range support
- `Glob`
- `Grep`
- `TodoWrite`
- `Write`
- `Edit`
- `NotebookEdit`
- `Bash`

## Current Limits

These limits are intentional at the current `nano` stage:

- No MCP
- No plugin system
- No multi-agent orchestration
- No IDE integration
- No remote execution
- No voice mode
- No rich TUI parity
- `Bash` currently runs locally without sandboxing

## Development

Run lint and tests:

```bash
ruff check .
pytest
```

## License

MIT
