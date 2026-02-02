from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.cyberagent.db import init_db
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.db.models.team import Team


def pytest_configure() -> None:
    tmp_root = Path(".pytest_db").resolve()
    tmp_root.mkdir(parents=True, exist_ok=True)
    db_path = tmp_root / "test.db"
    if db_path.exists():
        db_path.unlink()
    init_db.configure_database(f"sqlite:///{db_path}")
    init_db.init_db()
    session = next(get_db())
    try:
        team = Team(name="default_team", last_active_at=datetime.utcnow())
        session.add(team)
        session.commit()
        ensure_default_systems_for_team(team.id)
    finally:
        session.close()
