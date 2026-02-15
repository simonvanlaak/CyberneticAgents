from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.routing_rule import RoutingRule
from src.cyberagent.db.models.team import Team


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


def test_handle_onboarding_seeds_default_routing_rules_once(tmp_path: Path) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "run_discovery_onboarding", lambda *_: summary_path
    )

    onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
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
        rules = session.query(RoutingRule).filter(RoutingRule.team_id == team.id).all()
        assert len(rules) == 1
        assert rules[0].name == "Default DLQ"
    finally:
        session.close()


def test_handle_onboarding_seeds_procedure_routing_rules(tmp_path: Path) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli,
        "load_procedure_defaults",
        lambda: [
            {
                "name": "SOP With Routing",
                "description": "Test SOP.",
                "routing_rules": [
                    {
                        "name": "SOP Route",
                        "channel": "cli",
                        "filters": {"session_id": "cli-main"},
                        "targets": [{"system_id": "System4/root"}],
                        "priority": 5,
                    }
                ],
            }
        ],
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
        rules = session.query(RoutingRule).filter(RoutingRule.team_id == team.id).all()
        names = {rule.name for rule in rules}
        assert "SOP Route" in names
    finally:
        session.close()
