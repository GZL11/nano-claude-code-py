# nano-claude-code-py

An unofficial minimal terminal coding agent in Python.

`nano-claude-code-py` is a small, focused project that keeps only the core
agent loop:

`prompt -> model -> tool use -> local execution -> tool result -> final response`

It is not a full reimplementation of Claude Code. The goal is to build a
minimal, understandable, hackable Python codebase that can read files, edit
code, run shell commands, and hold a terminal conversation.

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
  - read file
  - list files
  - grep text
  - write file
  - edit file
- Shell execution tool with timeout and output capture
- Local transcript/session state
- Resume the latest local transcript
- Minimal permission modes:
  - `ask`
  - `auto-allow-read`
  - `danger-full-access`

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
    file_tools.py     # Read/list/write/edit tools
    shell_tools.py    # Shell execution tool
tests/
  test_registry.py
  test_file_tools.py
  test_shell_tools.py
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

### v0.3

- Better permission prompts
- Basic output formatting and tool activity display

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
nano-claude chat
```

Resume the latest saved transcript:

```bash
nano-claude resume
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
nano-claude run "summarize this repository"
```

## Development

Run lint and tests:

```bash
ruff check .
pytest
```

## License

MIT
