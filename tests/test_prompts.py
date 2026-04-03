from nano_claude_code_py.prompts import SYSTEM_PROMPT


def test_system_prompt_prefers_dedicated_tools_over_bash_equivalents():
    assert "File search: Use Glob, not find or ls." in SYSTEM_PROMPT
    assert "Content search: Use Grep, not grep or rg." in SYSTEM_PROMPT
    assert "Read files: Use Read, not cat/head/tail." in SYSTEM_PROMPT
    assert "Edit files: Use Edit, not sed/awk." in SYSTEM_PROMPT
    assert "Write files: Use Write, not echo redirection or heredocs." in SYSTEM_PROMPT


def test_system_prompt_keeps_source_aligned_todo_and_background_rules():
    assert "Use TodoWrite proactively for complex multi-step work" in SYSTEM_PROMPT
    assert "keep exactly one task in_progress at a time" in SYSTEM_PROMPT
    assert "For long-running shell commands, use `run_in_background`." in SYSTEM_PROMPT
