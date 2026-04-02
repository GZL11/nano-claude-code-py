from nano_claude_code_py.session import SessionTranscript


def test_transcript_to_plaintext_formats_messages():
    transcript = SessionTranscript()
    transcript.add("user", "hello")
    transcript.add("assistant", "world")

    output = transcript.to_plaintext()

    assert "## 1. user" in output
    assert "hello" in output
    assert "## 2. assistant" in output
    assert "world" in output
