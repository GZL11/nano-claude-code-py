import subprocess
import sys


def test_module_entrypoint_prints_version():
    result = subprocess.run(
        [sys.executable, "-m", "nano_claude_code_py", "version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "0.1.0" in result.stdout
