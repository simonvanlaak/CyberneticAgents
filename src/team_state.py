from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.db_utils import get_db
from src.models.system import ensure_default_systems_for_team
from src.models.team import Team

STATE_FILE = Path("data/last_team.json")


def read_last_team_id() -> Optional[int]:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
        return int(data.get("team_id"))
    except (ValueError, TypeError, KeyError):
        return None


def write_last_team_id(team_id: int) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"team_id": team_id}), encoding="utf-8")


def get_or_create_last_team_id() -> int:
    last_id = read_last_team_id()
    session = next(get_db())
    try:
        if last_id:
            team = session.query(Team).filter(Team.id == last_id).first()
            if team:
                ensure_default_systems_for_team(team.id)
                return team.id

        team = session.query(Team).order_by(Team.id.desc()).first()
        if team:
            write_last_team_id(team.id)
            ensure_default_systems_for_team(team.id)
            return team.id

        new_team = Team(name="default_team")
        session.add(new_team)
        session.commit()
        write_last_team_id(new_team.id)
        ensure_default_systems_for_team(new_team.id)
        return new_team.id
    finally:
        session.close()
