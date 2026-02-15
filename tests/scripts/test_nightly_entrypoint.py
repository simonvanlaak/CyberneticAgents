from __future__ import annotations

from pathlib import Path


def test_nightly_entrypoint_wraps_project_automation() -> None:
    """Nightly runner should delegate to the canonical lock wrapper."""

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "nightly-cyberneticagents.sh"

    assert script.exists(), "nightly-cyberneticagents.sh must exist"

    text = script.read_text(encoding="utf-8")
    assert "BASH_SOURCE" in text
    assert "run_project_automation.sh" in text
