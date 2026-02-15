from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_github_issue_queue_script_runs_from_any_cwd(tmp_path: Path) -> None:
    """Regression test: scripts/github_issue_queue.py must not depend on cwd."""

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "github_issue_queue.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Issue-label-based queue utilities" in result.stdout
