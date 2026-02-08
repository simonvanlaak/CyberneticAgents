from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from src.cyberagent.db.init_db import get_database_path


@dataclass(frozen=True)
class TeamMemberView:
    id: int
    name: str
    system_type: str
    agent_id_str: str


@dataclass(frozen=True)
class TeamWithMembersView:
    team_id: int
    team_name: str
    members: list[TeamMemberView]


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def load_teams_with_members(team_id: Optional[int] = None) -> list[TeamWithMembersView]:
    """
    Load teams and their system members sorted by team id and system id.
    """
    query = """
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            s.id AS system_id,
            s.name AS system_name,
            s.type AS system_type,
            s.agent_id_str AS system_agent_id
        FROM teams t
        LEFT JOIN systems s ON s.team_id = t.id
        WHERE 1 = 1
    """
    params: list[object] = []
    if team_id is not None:
        query += " AND t.id = ?"
        params.append(team_id)
    query += " ORDER BY t.id, s.id"

    conn = _connect_db()
    try:
        rows = conn.execute(query, tuple(params)).fetchall()
    finally:
        conn.close()

    grouped: dict[int, TeamWithMembersView] = {}
    for row in rows:
        row_team_id = int(row["team_id"])
        if row_team_id not in grouped:
            grouped[row_team_id] = TeamWithMembersView(
                team_id=row_team_id,
                team_name=str(row["team_name"]),
                members=[],
            )
        if row["system_id"] is None:
            continue
        grouped[row_team_id].members.append(
            TeamMemberView(
                id=int(row["system_id"]),
                name=str(row["system_name"]),
                system_type=str(row["system_type"]),
                agent_id_str=str(row["system_agent_id"]),
            )
        )
    return list(grouped.values())
