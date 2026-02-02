from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import recursions as recursions_service
from src.enums import SystemType


def _create_team_id() -> int:
    session = next(get_db())
    try:
        team = Team(name=f"recursion_team_{uuid4().hex}")
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


def test_create_recursion_logs_audit(caplog: pytest.LogCaptureFixture) -> None:
    parent_team_id = _create_team_id()
    sub_team_id = _create_team_id()
    origin_system_id = _create_system_id(parent_team_id)

    caplog.set_level(logging.INFO, logger="src.cyberagent.services.recursions")

    recursions_service.create_recursion(
        sub_team_id=sub_team_id,
        origin_system_id=origin_system_id,
        parent_team_id=parent_team_id,
        actor_id="system5/root",
    )

    assert any(
        record.message == "recursion_link_created"
        and record.__dict__.get("sub_team_id") == sub_team_id
        and record.__dict__.get("origin_system_id") == origin_system_id
        and record.__dict__.get("parent_team_id") == parent_team_id
        and record.__dict__.get("actor_id") == "system5/root"
        for record in caplog.records
    )
