from __future__ import annotations

import argparse

import pytest

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


def test_handle_onboarding_stops_when_foreground_discovery_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    monkeypatch.setattr(
        onboarding_cli,
        "run_discovery_onboarding",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setenv("CYBERAGENT_ONBOARDING_DISCOVERY_FOREGROUND", "1")
    monkeypatch.setattr(
        onboarding_cli, "start_onboarding_interview", lambda **_kwargs: None
    )
    start_calls: list[int] = []

    def _fake_start(team_id: int) -> int | None:
        start_calls.append(team_id)
        return 1234

    monkeypatch.setattr(onboarding_cli, "_start_runtime_after_onboarding", _fake_start)

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "couldn't complete" in captured.lower()
    assert start_calls == []
