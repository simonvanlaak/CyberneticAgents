from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func

from src.db_utils import get_db
from src.models.team import Team
from src.team_state import get_or_create_last_team_id, mark_team_active


def test_get_or_create_last_team_id_uses_last_active() -> None:
    session = next(get_db())
    try:
        latest = session.query(func.max(Team.last_active_at)).scalar()
        baseline = latest or datetime.utcnow()
        older = Team(
            name=f"older_team_{uuid4().hex}",
            last_active_at=baseline - timedelta(hours=2),
        )
        newer = Team(
            name=f"newer_team_{uuid4().hex}",
            last_active_at=baseline + timedelta(minutes=5),
        )
        session.add_all([older, newer])
        session.commit()
        newer_id = newer.id
    finally:
        session.close()

    assert get_or_create_last_team_id() == newer_id


def test_mark_team_active_updates_timestamp() -> None:
    session = next(get_db())
    try:
        team = Team(
            name=f"active_team_{uuid4().hex}",
            last_active_at=datetime.utcnow() - timedelta(days=1),
        )
        session.add(team)
        session.commit()
        team_id = team.id
    finally:
        session.close()

    mark_team_active(team_id)

    session = next(get_db())
    try:
        refreshed = session.query(Team).filter(Team.id == team_id).first()
        assert refreshed is not None
        assert refreshed.last_active_at is not None
        assert refreshed.last_active_at >= datetime.utcnow() - timedelta(minutes=1)
    finally:
        session.close()
