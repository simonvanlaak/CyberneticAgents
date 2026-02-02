from __future__ import annotations

from uuid import uuid4

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import recursions as recursions_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType


def _create_team_id(name: str | None = None) -> int:
    session = next(get_db())
    try:
        team = Team(name=name or f"skill_team_{uuid4().hex}")
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


def _get_or_create_root_team_id() -> int:
    session = next(get_db())
    try:
        existing = session.query(Team).filter(Team.name == "default_team").first()
        if existing:
            return existing.id
        team = Team(name="default_team")
        session.add(team)
        session.commit()
        return team.id
    finally:
        session.close()


def test_root_team_bypass_allows_grant_and_execute() -> None:
    root_team_id = _get_or_create_root_team_id()
    system_id = _create_system_id(root_team_id)

    assert (
        systems_service.add_skill_grant(
            system_id=system_id,
            skill_name="skill.root",
            actor_id="system5/root",
        )
        is True
    )

    allowed, reason = systems_service.can_execute_skill(system_id, "skill.root")

    assert allowed is True
    assert reason is None


def test_envelope_revoke_cascades_system_grants() -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)

    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.cascade",
        actor_id="system5/root",
    )
    systems_service.add_skill_grant(
        system_id=system_id,
        skill_name="skill.cascade",
        actor_id="system5/root",
    )

    revoked = teams_service.remove_allowed_skill(
        team_id=team_id,
        skill_name="skill.cascade",
        actor_id="system5/root",
    )

    assert revoked == 1
    assert systems_service.list_granted_skills(system_id) == []


def test_deep_recursion_inherits_origin_grants() -> None:
    root_team_id = _get_or_create_root_team_id()
    parent_team_id = _create_team_id()
    child_team_id = _create_team_id()

    root_origin_system_id = _create_system_id(root_team_id)
    parent_origin_system_id = _create_system_id(parent_team_id)
    child_system_id = _create_system_id(child_team_id)

    recursions_service.create_recursion(
        sub_team_id=parent_team_id,
        origin_system_id=root_origin_system_id,
        parent_team_id=root_team_id,
        actor_id="system5/root",
    )
    recursions_service.create_recursion(
        sub_team_id=child_team_id,
        origin_system_id=parent_origin_system_id,
        parent_team_id=parent_team_id,
        actor_id="system5/root",
    )

    for team_id in (root_team_id, parent_team_id, child_team_id):
        teams_service.add_allowed_skill(
            team_id=team_id,
            skill_name="skill.recursive",
            actor_id="system5/root",
        )

    systems_service.add_skill_grant(
        system_id=root_origin_system_id,
        skill_name="skill.recursive",
        actor_id="system5/root",
    )
    systems_service.add_skill_grant(
        system_id=parent_origin_system_id,
        skill_name="skill.recursive",
        actor_id="system5/root",
    )
    systems_service.add_skill_grant(
        system_id=child_system_id,
        skill_name="skill.recursive",
        actor_id="system5/root",
    )

    allowed, reason = systems_service.can_execute_skill(
        child_system_id, "skill.recursive"
    )
    assert allowed is True
    assert reason is None

    systems_service.remove_skill_grant(
        system_id=root_origin_system_id,
        skill_name="skill.recursive",
        actor_id="system5/root",
    )

    allowed, reason = systems_service.can_execute_skill(
        child_system_id, "skill.recursive"
    )
    assert allowed is False
    assert reason == "system_grant"
