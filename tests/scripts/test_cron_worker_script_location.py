from __future__ import annotations

from pathlib import Path


def test_cron_worker_cd_is_repo_root() -> None:
    """Regression test: cron worker must operate from repo root.

    The automation requires all gh/git/script calls to be executed in the repo
    directory (not /root/.openclaw/workspace).
    """

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "cron_cyberneticagents_worker.sh"
    text = script.read_text(encoding="utf-8")

    assert "cd /root/.openclaw/workspace" not in text
    assert "BASH_SOURCE" in text
    assert "$REPO_ROOT/.venv/bin/python" in text
    assert '"$PYTHON" ./scripts/github_outbox.py' in text
