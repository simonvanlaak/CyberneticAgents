from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.procedure_run import ProcedureRun
from src.cyberagent.db.models.procedure_task import ProcedureTask
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import teams as teams_service


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


def test_handle_onboarding_syncs_root_team_envelope_from_defaults(
    tmp_path: Path,
) -> None:
    _clear_teams()
    session = next(get_db())
    try:
        session.add(Team(name="existing_team"))
        session.add(Team(name="root"))
        session.commit()
    finally:
        session.close()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )

    onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    monkeypatch.undo()

    defaults = onboarding_cli.load_root_team_defaults()
    configured = defaults.get("allowed_skills")
    assert isinstance(configured, list)
    expected = {skill for skill in configured if isinstance(skill, str)}

    session = next(get_db())
    try:
        root = session.query(Team).filter(Team.name == "root").first()
        assert root is not None
        allowed = set(teams_service.list_allowed_skills(root.id))
        assert allowed == expected
    finally:
        session.close()
