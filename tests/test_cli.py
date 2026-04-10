import os
import subprocess
import sys


def test_module_cli_help_smoke():
    result = subprocess.run(
        [sys.executable, "-m", "wbmbot_v3.main", "--help"],
        capture_output=True,
        text=True,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        check=False,
        env={**os.environ, "PYTHONPATH": "."},
    )

    assert result.returncode == 0
    assert "python -m wbmbot_v3" in result.stdout
