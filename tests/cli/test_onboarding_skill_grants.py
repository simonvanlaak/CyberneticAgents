from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(Team).delete()
        session.commit()
    finally:
        session.close()


def _default_onboarding_args() -> onboarding_cli.argparse.Namespace:
    args = onboarding_cli.argparse.Namespace()
    args.user_name = "Simon"
    args.repo_url = "https://github.com/example/repo"
    args.profile_links = ["example.com"]
    return args


def test_handle_onboarding_seeds_system1_with_pkm_access_skills(tmp_path: Path) -> None:
    """System1 should be able to sync and read PKM content after onboarding."""

    _clear_teams()
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

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        system1 = (
            session.query(System)
            .filter(System.team_id == team.id, System.agent_id_str == "System1/root")
            .first()
        )
        assert system1 is not None
    finally:
        session.close()

    # Team envelope must allow the skills.
    allowed = set(teams_service.list_allowed_skills(team.id))
    assert {"git-readonly-sync", "file-reader", "notion"}.issubset(allowed)

    # System1 should have grants needed to sync + load PKM details.
    grants = set(systems_service.list_granted_skills(system1.id))
    assert {"memory_crud", "git-readonly-sync", "file-reader", "notion"}.issubset(
        grants
    )
