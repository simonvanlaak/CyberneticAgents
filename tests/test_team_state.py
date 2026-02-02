from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import func

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.team import Team
from src.cyberagent.core import state
from src.cyberagent.core.state import get_last_team_id, mark_team_active


def test_get_last_team_id_uses_last_active() -> None:
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

    assert get_last_team_id() == newer_id


def test_get_last_team_id_returns_none_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyQuery:
        def order_by(self, *args: object, **kwargs: object) -> "DummyQuery":
            return self

        def first(self) -> None:
            return None

    class DummySession:
        def __init__(self) -> None:
            self.commit_called = False
            self.closed = False

        def query(self, *args: object, **kwargs: object) -> DummyQuery:
            return DummyQuery()

        def commit(self) -> None:
            self.commit_called = True

        def close(self) -> None:
            self.closed = True

    session = DummySession()

    def fake_get_db() -> Iterator[DummySession]:
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(state, "get_db", fake_get_db)

    assert get_last_team_id() is None
    assert session.commit_called is False
    assert session.closed is True


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
