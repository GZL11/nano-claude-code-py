from nano_claude_code_py.session import (
    SessionTranscript,
    default_session_path,
    latest_session_path,
    list_sessions,
    load_latest_session,
    load_selected_session,
)


def test_load_latest_session_returns_latest_file(tmp_path):
    first = default_session_path(tmp_path)
    transcript_a = SessionTranscript()
    transcript_a.add("user", "first")
    transcript_a.save_jsonl(first)

    second = tmp_path / "99999999-999999.jsonl"
    transcript_b = SessionTranscript()
    transcript_b.add("user", "second")
    transcript_b.save_jsonl(second)

    loaded, path = load_latest_session(tmp_path)

    assert path == second
    assert loaded.messages[-1].text_content() == "second"


def test_latest_session_path_returns_none_for_empty_directory(tmp_path):
    assert latest_session_path(tmp_path) is None


def test_list_sessions_returns_newest_first(tmp_path):
    older = tmp_path / "20240101-000000.jsonl"
    newer = tmp_path / "20240102-000000.jsonl"

    transcript_a = SessionTranscript()
    transcript_a.add("user", "older")
    transcript_a.save_jsonl(older)

    transcript_b = SessionTranscript()
    transcript_b.add("user", "newer")
    transcript_b.save_jsonl(newer)

    sessions = list_sessions(tmp_path)

    assert sessions[0].path == newer
    assert sessions[1].path == older


def test_load_selected_session_by_index_and_name(tmp_path):
    first = tmp_path / "20240101-000000.jsonl"
    second = tmp_path / "20240102-000000.jsonl"

    transcript_a = SessionTranscript()
    transcript_a.add("user", "first")
    transcript_a.save_jsonl(first)

    transcript_b = SessionTranscript()
    transcript_b.add("user", "second")
    transcript_b.save_jsonl(second)

    by_index, path_by_index = load_selected_session(tmp_path, index=2)
    by_name, path_by_name = load_selected_session(tmp_path, name=second.stem)

    assert path_by_index == first
    assert by_index.messages[-1].text_content() == "first"
    assert path_by_name == second
    assert by_name.messages[-1].text_content() == "second"
