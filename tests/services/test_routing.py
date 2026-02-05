from __future__ import annotations

from datetime import datetime

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.team import Team
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.services import recursions as recursions_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import routing as routing_service
from src.enums import SystemType


def _create_team(name: str) -> Team:
    session = next(get_db())
    try:
        team = Team(name=name, last_active_at=datetime.utcnow())
        session.add(team)
        session.commit()
        ensure_default_systems_for_team(team.id)
        return team
    finally:
        session.close()


def test_match_routing_rules_exact() -> None:
    team = _create_team("routing_team")
    routing_service.create_routing_rule(
        team_id=team.id,
        name="telegram_user_match",
        channel="telegram",
        filters={"telegram_user_id": "123"},
        targets=[{"system_id": "System4/root"}],
        priority=10,
    )
    routing_service.create_routing_rule(
        team_id=team.id,
        name="telegram_user_other",
        channel="telegram",
        filters={"telegram_user_id": "999"},
        targets=[{"system_id": "System4/root"}],
        priority=5,
    )

    matched = routing_service.match_routing_rules(
        team_id=team.id,
        channel="telegram",
        metadata={"telegram_user_id": "123"},
    )

    assert [rule.name for rule in matched] == ["telegram_user_match"]


def test_route_message_to_system() -> None:
    team = _create_team("routing_system_team")
    system4 = systems_service.get_system_by_type(team.id, SystemType.INTELLIGENCE)
    assert system4 is not None

    routing_service.create_routing_rule(
        team_id=team.id,
        name="all_to_system4",
        channel="*",
        filters={},
        targets=[{"system_id": system4.id}],
        priority=1,
    )

    resolved = routing_service.resolve_message_targets(
        team_id=team.id,
        channel="cli",
        metadata={"session_id": "cli-main"},
    )

    assert resolved == [system4.agent_id_str]


def test_route_message_to_subteam() -> None:
    parent = _create_team("routing_parent")
    child = _create_team("routing_child")
    parent_system5 = systems_service.get_system_by_type(parent.id, SystemType.POLICY)
    assert parent_system5 is not None

    recursions_service.create_recursion(
        sub_team_id=child.id,
        parent_team_id=parent.id,
        origin_system_id=parent_system5.id,
        created_by="tests",
    )

    routing_service.create_routing_rule(
        team_id=parent.id,
        name="to_child",
        channel="telegram",
        filters={"telegram_user_id": "42"},
        targets=[{"team_id": child.id}],
        priority=5,
    )
    child_systems1 = systems_service.get_systems_by_type(child.id, SystemType.OPERATION)
    assert child_systems1
    child_system1 = child_systems1[0]
    routing_service.create_routing_rule(
        team_id=child.id,
        name="child_to_system1",
        channel="telegram",
        filters={"telegram_user_id": "42"},
        targets=[{"system_id": child_system1.id}],
        priority=5,
    )

    resolved = routing_service.resolve_message_targets(
        team_id=parent.id,
        channel="telegram",
        metadata={"telegram_user_id": "42"},
    )

    assert resolved == [child_system1.agent_id_str]


def test_dlq_when_no_route() -> None:
    team = _create_team("routing_dlq_team")
    system4 = systems_service.get_system_by_type(team.id, SystemType.INTELLIGENCE)
    assert system4 is not None

    resolved = routing_service.resolve_message_targets(
        team_id=team.id,
        channel="cli",
        metadata={"session_id": "cli-main"},
    )

    assert resolved == [system4.agent_id_str]
    dlq_entries = routing_service.list_dead_letters(team_id=team.id, status="pending")
    assert len(dlq_entries) == 1
