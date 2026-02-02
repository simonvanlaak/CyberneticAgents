from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import recursions as recursions_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType
from src.rbac import skill_permissions_enforcer


def _create_team_id(name: str | None = None) -> int:
    session = next(get_db())
    try:
        team = Team(name=name or f"audit_team_{uuid4().hex}")
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


def test_audit_logs_for_recursion_and_execution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parent_team_id = _create_team_id()
    sub_team_id = _create_team_id()
    origin_system_id = _create_system_id(parent_team_id)
    sub_system_id = _create_system_id(sub_team_id)

    caplog.set_level(logging.INFO, logger="src.cyberagent.services.recursions")
    caplog.set_level(logging.INFO, logger="src.cyberagent.services.systems")

    recursions_service.create_recursion(
        sub_team_id=sub_team_id,
        origin_system_id=origin_system_id,
        parent_team_id=parent_team_id,
        actor_id="system5/root",
    )

    for team_id in (parent_team_id, sub_team_id):
        teams_service.add_allowed_skill(
            team_id=team_id,
            skill_name="skill.audit",
            actor_id="system5/root",
        )
        assert "skill.audit" in teams_service.list_allowed_skills(team_id)

    systems_service.add_skill_grant(
        system_id=origin_system_id,
        skill_name="skill.audit",
        actor_id="system5/root",
    )
    systems_service.add_skill_grant(
        system_id=sub_system_id,
        skill_name="skill.audit",
        actor_id="system5/root",
    )
    assert "skill.audit" in systems_service.list_granted_skills(origin_system_id)
    assert "skill.audit" in systems_service.list_granted_skills(sub_system_id)
    enforcer = skill_permissions_enforcer.get_enforcer()
    assert enforcer.enforce(
        f"system:{origin_system_id}",
        str(parent_team_id),
        "skill:skill.audit",
        "allow",
    )
    assert enforcer.enforce(
        f"system:{sub_system_id}",
        str(sub_team_id),
        "skill:skill.audit",
        "allow",
    )

    allowed, reason = systems_service.can_execute_skill(sub_system_id, "skill.audit")

    assert allowed is True, f"Expected allow but got {reason}"
    assert reason is None

    assert any(
        record.message == "recursion_link_created"
        and record.__dict__.get("sub_team_id") == sub_team_id
        and record.__dict__.get("origin_system_id") == origin_system_id
        and record.__dict__.get("parent_team_id") == parent_team_id
        for record in caplog.records
    )

    assert any(
        record.message == "skill_permission_decision"
        and record.__dict__.get("team_id") == sub_team_id
        and record.__dict__.get("system_id") == sub_system_id
        and record.__dict__.get("skill_name") == "skill.audit"
        and record.__dict__.get("allowed") is True
        for record in caplog.records
    )
