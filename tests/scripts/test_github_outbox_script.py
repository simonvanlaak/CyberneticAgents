from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_github_outbox_script_runs_from_any_cwd(tmp_path: Path) -> None:
    """Regression test: scripts/github_outbox.py must not depend on cwd.

    The cron worker invokes it from repo-adjacent directories.
    """

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "github_outbox.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Rate-limit-aware GitHub outbox" in result.stdout
