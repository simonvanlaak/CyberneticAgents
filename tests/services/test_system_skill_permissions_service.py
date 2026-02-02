from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType
from src.rbac import skill_permissions_enforcer


@pytest.fixture(autouse=True)
def _reset_skill_permissions_enforcer(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    skill_permissions_enforcer._global_enforcer = None
    enforcer = skill_permissions_enforcer.get_enforcer()
    enforcer.clear_policy()
    yield
    skill_permissions_enforcer._global_enforcer = None


def _create_team_id() -> int:
    session = next(get_db())
    try:
        team = Team(name=f"skill_team_{uuid4().hex}")
        session.add(team)
        session.commit()
        return team.id
    finally:
        session.close()


def _create_system_id(team_id: int) -> int:
    session = next(get_db())
    try:
        system = System(
            team_id=team_id,
            name=f"system_{uuid4().hex}",
            type=SystemType.OPERATION,
            agent_id_str=f"team{team_id}_ops_{uuid4().hex}",
        )
        session.add(system)
        session.commit()
        return system.id
    finally:
        session.close()


def test_add_skill_grant_requires_team_envelope() -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)

    with pytest.raises(PermissionError, match="team_envelope"):
        systems_service.add_skill_grant(
            system_id=system_id,
            skill_name="skill.gamma",
            actor_id="system5/root",
        )

    assert systems_service.list_granted_skills(system_id) == []


def test_add_skill_grant_enforces_max_limit() -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)

    for index in range(6):
        teams_service.add_allowed_skill(
            team_id=team_id,
            skill_name=f"skill.limit.{index}",
            actor_id="system5/root",
        )

    for index in range(5):
        assert (
            systems_service.add_skill_grant(
                system_id=system_id,
                skill_name=f"skill.limit.{index}",
                actor_id="system5/root",
            )
            is True
        )

    with pytest.raises(PermissionError, match="system_skill_limit"):
        systems_service.add_skill_grant(
            system_id=system_id,
            skill_name="skill.limit.5",
            actor_id="system5/root",
        )

    assert len(systems_service.list_granted_skills(system_id)) == 5


def test_can_execute_skill_deny_precedence() -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)

    allowed, reason = systems_service.can_execute_skill(system_id, "skill.delta")
    assert allowed is False
    assert reason == "team_envelope"

    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.delta",
        actor_id="system5/root",
    )

    allowed, reason = systems_service.can_execute_skill(system_id, "skill.delta")
    assert allowed is False
    assert reason == "system_grant"

    systems_service.add_skill_grant(
        system_id=system_id,
        skill_name="skill.delta",
        actor_id="system5/root",
    )

    allowed, reason = systems_service.can_execute_skill(system_id, "skill.delta")
    assert allowed is True
    assert reason is None


def test_can_execute_skill_logs_decision(caplog: pytest.LogCaptureFixture) -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)

    caplog.set_level(logging.INFO, logger="src.cyberagent.services.systems")

    allowed, reason = systems_service.can_execute_skill(system_id, "skill.log")

    assert allowed is False
    assert reason == "team_envelope"
    assert any(
        record.message == "skill_permission_decision"
        and record.__dict__.get("team_id") == team_id
        and record.__dict__.get("system_id") == system_id
        and record.__dict__.get("skill_name") == "skill.log"
        and record.__dict__.get("allowed") is False
        and record.__dict__.get("failed_rule_category") == "team_envelope"
        for record in caplog.records
    )
