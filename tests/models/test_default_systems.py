from __future__ import annotations

from uuid import uuid4

from src.db_utils import get_db
from src.enums import SystemType
from src.models.system import ensure_default_systems_for_team, get_systems_by_type
from src.models.team import Team


def test_ensure_default_systems_for_team_creates_missing() -> None:
    session = next(get_db())
    try:
        team = Team(name=f"default_systems_{uuid4().hex}")
        session.add(team)
        session.commit()
        team_id = team.id
    finally:
        session.close()

    ensure_default_systems_for_team(team_id)

    for system_type in (
        SystemType.OPERATION,
        SystemType.CONTROL,
        SystemType.INTELLIGENCE,
        SystemType.POLICY,
    ):
        systems = get_systems_by_type(team_id, system_type)
        assert systems, f"Expected a default system for {system_type}."
