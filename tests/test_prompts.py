from nano_claude_code_py.prompts import (
    SYSTEM_PROMPT,
    build_system_prompt,
    normalize_language,
)


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


def test_system_prompt_supports_chinese_language_directive():
    prompt = build_system_prompt("zh")

    assert "Always respond in Chinese." in prompt
    assert "Keep code, file paths, commands, and API identifiers" in prompt


def test_system_prompt_supports_japanese_and_korean_language_directives():
    japanese_prompt = build_system_prompt("ja")
    korean_prompt = build_system_prompt("ko")

    assert "Always respond in Japanese." in japanese_prompt
    assert "Always respond in Korean." in korean_prompt


def test_normalize_language_defaults_unknown_values_to_english():
    assert normalize_language(None) == "english"
    assert normalize_language("english") == "english"
    assert normalize_language("中文") == "chinese"
    assert normalize_language("zh-CN") == "chinese"
    assert normalize_language("日本語") == "japanese"
    assert normalize_language("ja-JP") == "japanese"
    assert normalize_language("한국어") == "korean"
    assert normalize_language("ko-KR") == "korean"
    assert normalize_language("unknown") == "english"
