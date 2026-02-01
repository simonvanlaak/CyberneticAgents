from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import ensure_default_systems_for_team
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


def get_or_create_last_team_id() -> int:
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
            ensure_default_systems_for_team(team.id)
            return team.id

        new_team = Team(
            name="default_team",
            last_active_at=datetime.utcnow(),
        )
        session.add(new_team)
        session.commit()
        ensure_default_systems_for_team(new_team.id)
        return new_team.id
    finally:
        session.close()
