from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import recover_sqlite_database
from src.cyberagent.db.models.team import Team
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def mark_team_active(team_id: int) -> None:
    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.id == team_id).first()
        if team is None:
            raise ValueError(f"Team id {team_id} is not registered.")
        team.last_active_at = datetime.utcnow()
        _commit_with_recovery(session, "mark_team_active")
    finally:
        session.close()


def get_last_team_id() -> Optional[int]:
    session = next(get_db())
    try:
        team = (
            session.query(Team)
            .order_by(
                Team.last_active_at.is_(None),
                Team.last_active_at.desc(),
                Team.id.desc(),
            )
            .first()
        )
        if team:
            team.last_active_at = datetime.utcnow()
            _commit_with_recovery(session, "get_last_team_id")
            return team.id
        return None
    finally:
        session.close()


def _commit_with_recovery(session, action: str) -> None:
    try:
        session.commit()
        return
    except OperationalError as exc:
        session.rollback()
        if "disk i/o" in str(exc).lower():
            backup = recover_sqlite_database()
            if backup:
                logger.warning(
                    "Recovered SQLite database during %s (backup=%s).",
                    action,
                    backup,
                )
            try:
                session.commit()
                return
            except OperationalError:
                session.rollback()
        logger.exception("Database write failed during %s.", action)
