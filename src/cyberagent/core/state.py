from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.team import Team


def mark_team_active(team_id: int) -> None:
    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.id == team_id).first()
        if team is None:
            raise ValueError(f"Team id {team_id} is not registered.")
        team.last_active_at = datetime.utcnow()
        session.commit()
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
            session.commit()
            return team.id
        return None
    finally:
        session.close()
