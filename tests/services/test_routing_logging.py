from __future__ import annotations

from datetime import datetime

import pytest

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.team import Team
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.services import routing as routing_service


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


def test_routing_logs_match_event(caplog: pytest.LogCaptureFixture) -> None:
    team = _create_team("routing_log_match")
    routing_service.create_routing_rule(
        team_id=team.id,
        name="log-match",
        channel="telegram",
        filters={"telegram_user_id": "123"},
        targets=[{"system_id": "System4/root"}],
        priority=10,
    )

    with caplog.at_level("INFO"):
        routing_service.resolve_message_decision(
            team_id=team.id,
            channel="telegram",
            metadata={"telegram_user_id": "123"},
        )

    assert any(record.message == "routing_match" for record in caplog.records)


def test_routing_logs_dlq_event(caplog: pytest.LogCaptureFixture) -> None:
    team = _create_team("routing_log_dlq")
    with caplog.at_level("INFO"):
        decision = routing_service.resolve_message_decision(
            team_id=team.id,
            channel="cli",
            metadata={"session_id": "cli-main"},
        )

    assert decision.dlq_entry_id is not None
    assert any(record.message == "routing_dlq" for record in caplog.records)
