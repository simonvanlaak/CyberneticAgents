from __future__ import annotations

from datetime import datetime

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.ui.teams_data import load_teams_with_members
from src.enums import SystemType


def _create_team(name: str) -> int:
    session = next(get_db())
    try:
        team = Team(name=name, last_active_at=datetime.utcnow())
        session.add(team)
        session.commit()
        session.refresh(team)
        return int(team.id)
    finally:
        session.close()


def _create_system(
    *, team_id: int, name: str, system_type: SystemType, agent_id_str: str
) -> int:
    session = next(get_db())
    try:
        system = System(
            team_id=team_id,
            name=name,
            type=system_type,
            agent_id_str=agent_id_str,
        )
        session.add(system)
        session.commit()
        session.refresh(system)
        return int(system.id)
    finally:
        session.close()


def test_load_teams_with_members_orders_teams_and_members() -> None:
    team_a = _create_team("ui-team-a")
    team_b = _create_team("ui-team-b")

    sys_b1 = _create_system(
        team_id=team_b,
        name="System4/ui-b",
        system_type=SystemType.INTELLIGENCE,
        agent_id_str="System4/ui-b",
    )
    sys_a1 = _create_system(
        team_id=team_a,
        name="System3/ui-a",
        system_type=SystemType.CONTROL,
        agent_id_str="System3/ui-a",
    )

    rows = [
        row
        for row in load_teams_with_members()
        if row.team_name in {"ui-team-a", "ui-team-b"}
    ]
    assert [row.team_id for row in rows] == [team_a, team_b]
    assert [member.id for member in rows[0].members] == [sys_a1]
    assert [member.id for member in rows[1].members] == [sys_b1]


def test_load_teams_with_members_can_filter_by_team_id() -> None:
    team = _create_team("ui-team-filter")
    _create_system(
        team_id=team,
        name="System1/ui-filter",
        system_type=SystemType.OPERATION,
        agent_id_str="System1/ui-filter",
    )

    filtered = load_teams_with_members(team_id=team)
    assert len(filtered) == 1
    assert filtered[0].team_id == team
    assert filtered[0].team_name == "ui-team-filter"
    assert len(filtered[0].members) == 1
