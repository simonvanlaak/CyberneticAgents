from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType
from src.cyberagent.authz import skill_permissions_enforcer


@pytest.fixture(autouse=True)
def _reset_skill_permissions_enforcer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
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


def test_team_envelope_crud_round_trip() -> None:
    team_id = _create_team_id()

    assert teams_service.list_allowed_skills(team_id) == []

    added = teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.alpha",
        actor_id="system5/root",
    )
    assert added is True
    assert set(teams_service.list_allowed_skills(team_id)) == {"skill.alpha"}

    removed_count = teams_service.remove_allowed_skill(
        team_id=team_id,
        skill_name="skill.alpha",
        actor_id="system5/root",
    )
    assert removed_count == 0
    assert teams_service.list_allowed_skills(team_id) == []


def test_remove_allowed_skill_cascades_system_grants() -> None:
    team_id = _create_team_id()
    system_id = _create_system_id(team_id)

    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.beta",
        actor_id="system5/root",
    )

    assert (
        systems_service.add_skill_grant(
            system_id=system_id,
            skill_name="skill.beta",
            actor_id="system5/root",
        )
        is True
    )

    removed_count = teams_service.remove_allowed_skill(
        team_id=team_id,
        skill_name="skill.beta",
        actor_id="system5/root",
    )

    assert removed_count == 1
    assert systems_service.list_granted_skills(system_id) == []


def test_team_envelope_add_logs_audit(caplog: pytest.LogCaptureFixture) -> None:
    team_id = _create_team_id()

    caplog.set_level(logging.INFO, logger="src.cyberagent.services.teams")

    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.audit",
        actor_id="system5/root",
    )

    assert any(
        record.message == "skill_envelope_add"
        and record.__dict__.get("team_id") == team_id
        and record.__dict__.get("skill_name") == "skill.audit"
        and record.__dict__.get("actor_id") == "system5/root"
        for record in caplog.records
    )


def test_team_envelope_logs_audit_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    team_id = _create_team_id()
    caplog.set_level(logging.INFO, logger="src.cyberagent.services.teams")

    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="skill.audit",
        actor_id="system5/root",
    )
    teams_service.remove_allowed_skill(
        team_id=team_id,
        skill_name="skill.audit",
        actor_id="system5/root",
    )

    assert any(
        record.message == "skill_envelope_add"
        and record.__dict__.get("team_id") == team_id
        and record.__dict__.get("skill_name") == "skill.audit"
        and record.__dict__.get("actor_id") == "system5/root"
        for record in caplog.records
    )
    assert any(
        record.message == "skill_envelope_remove"
        and record.__dict__.get("team_id") == team_id
        and record.__dict__.get("skill_name") == "skill.audit"
        and record.__dict__.get("actor_id") == "system5/root"
        for record in caplog.records
    )
