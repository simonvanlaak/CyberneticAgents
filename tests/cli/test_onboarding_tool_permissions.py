from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.rbac import enforcer as tools_rbac_enforcer


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(System).delete()
        session.query(Team).delete()
        session.commit()
        session.add(Team(name="default_team", last_active_at=datetime.utcnow()))
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


def test_handle_onboarding_grants_legacy_tool_permission_for_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_teams()
    monkeypatch.setenv("CYBERAGENT_RBAC_DB_URL", f"sqlite:///{tmp_path / 'rbac.db'}")
    tools_rbac_enforcer._global_enforcer = None
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "run_discovery_onboarding", lambda *_: summary_path
    )

    try:
        exit_code = onboarding_cli.handle_onboarding(
            _default_onboarding_args(),
            'cyberagent suggest "Describe the task"',
            "cyberagent inbox",
        )
        assert exit_code == 0
        assert (
            tools_rbac_enforcer.check_tool_permission(
                "System4/root", "git-readonly-sync"
            )
            is True
        )
    finally:
        tools_rbac_enforcer._global_enforcer = None
