from __future__ import annotations

import argparse
from pathlib import Path

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.procedure_run import ProcedureRun
from src.cyberagent.db.models.procedure_task import ProcedureTask
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(ProcedureTask).delete()
        session.query(ProcedureRun).delete()
        session.query(Procedure).delete()
        session.query(System).delete()
        session.query(Team).delete()
        session.commit()
    finally:
        session.close()


def _default_onboarding_args() -> argparse.Namespace:
    return argparse.Namespace(
        user_name="Test User",
        pkm_source="github",
        repo_url="https://github.com/example/repo",
        profile_links=["https://example.com/profile"],
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )


def test_onboarding_runs_discovery_before_initiative_trigger(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_teams()
    sequence: list[str] = []
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")

    def _fake_discovery(*_args, **_kwargs):
        sequence.append("discovery")
        return summary_path

    def _fake_trigger(*_args, **_kwargs):
        sequence.append("trigger")
        return True

    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "start_onboarding_interview", lambda **_kw: None
    )
    monkeypatch.setattr(onboarding_cli, "_run_discovery_onboarding", _fake_discovery)
    monkeypatch.setattr(onboarding_cli, "_trigger_onboarding_initiative", _fake_trigger)
    monkeypatch.setattr(
        onboarding_cli, "_start_runtime_after_onboarding", lambda *_: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_start_dashboard_after_onboarding", lambda *_: None
    )

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )

    assert exit_code == 0
    assert sequence == ["discovery", "trigger"]
