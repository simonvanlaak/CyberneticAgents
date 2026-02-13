from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from src.cyberagent.authz import (
    allow_skill_for_team,
    grant_skill_to_system,
    grant_tool_permission,
    has_tool_permission,
    is_system_skill_granted,
    is_team_skill_allowed,
    list_system_granted_skills,
    list_team_allowed_skills,
    reload_skill_policy_store,
)
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.enums import SystemType
from src.rbac import enforcer as tools_rbac_enforcer
from src.rbac import skill_permissions_enforcer


@pytest.fixture(autouse=True)
def _reset_tool_enforcer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv("CYBERAGENT_RBAC_DB_URL", f"sqlite:///{tmp_path / 'rbac.db'}")
    tools_rbac_enforcer._global_enforcer = None
    yield
    tools_rbac_enforcer._global_enforcer = None


@pytest.fixture(autouse=True)
def _reset_skill_enforcer() -> Iterator[None]:
    skill_permissions_enforcer._global_enforcer = None
    enforcer = skill_permissions_enforcer.get_enforcer()
    enforcer.clear_policy()
    yield
    skill_permissions_enforcer._global_enforcer = None


def _create_team_and_system() -> tuple[int, int]:
    session = next(get_db())
    try:
        team = Team(name="facade_team")
        session.add(team)
        session.commit()

        system = System(
            team_id=team.id,
            name="facade_system",
            type=SystemType.OPERATION,
            agent_id_str="facade_ops_sys1",
        )
        session.add(system)
        session.commit()
        return team.id, system.id
    finally:
        session.close()


def test_tool_permission_grant_and_check() -> None:
    assert has_tool_permission("facade_ops_sys1", "web-fetch") is False

    grant_tool_permission("facade_ops_sys1", "web-fetch", "*")

    assert has_tool_permission("facade_ops_sys1", "web-fetch") is True


def test_skill_permission_facade_round_trip() -> None:
    team_id, system_id = _create_team_and_system()

    assert list_team_allowed_skills(team_id) == []
    assert list_system_granted_skills(system_id) == []

    allow_skill_for_team(team_id, "skill.example")
    grant_skill_to_system(system_id, team_id, "skill.example")

    assert is_team_skill_allowed(team_id, "skill.example") is True
    assert is_system_skill_granted(system_id, team_id, "skill.example") is True
    assert list_team_allowed_skills(team_id) == ["skill.example"]
    assert list_system_granted_skills(system_id) == ["skill.example"]


def test_reload_skill_policy_store_restores_cleared_cache() -> None:
    team_id, system_id = _create_team_and_system()
    allow_skill_for_team(team_id, "skill.reload")
    grant_skill_to_system(system_id, team_id, "skill.reload")

    enforcer = skill_permissions_enforcer.get_enforcer()
    enforcer.clear_policy()

    assert is_system_skill_granted(system_id, team_id, "skill.reload") is False

    reload_skill_policy_store()

    assert is_system_skill_granted(system_id, team_id, "skill.reload") is True
