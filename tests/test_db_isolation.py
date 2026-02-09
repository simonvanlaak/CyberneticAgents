from __future__ import annotations

from datetime import datetime

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.team import Team


def test_db_isolation_seed_leak_setup() -> None:
    session = next(get_db())
    try:
        session.add(Team(name="leak_probe_team", last_active_at=datetime.utcnow()))
        session.commit()
    finally:
        session.close()


def test_db_isolation_seed_leak_assert() -> None:
    session = next(get_db())
    try:
        leaked = (
            session.query(Team).filter(Team.name == "leak_probe_team").first()
            is not None
        )
    finally:
        session.close()

    assert leaked is False
