from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from src.cyberagent.db.init_db import get_database_path
from src.rbac.skill_permissions_enforcer import get_enforcer


@dataclass(frozen=True)
class TeamMemberView:
    id: int
    name: str
    system_type: str
    agent_id_str: str
    policies: list[str]
    permissions: list[str]


@dataclass(frozen=True)
class TeamWithMembersView:
    team_id: int
    team_name: str
    policies: list[str]
    permissions: list[str]
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
                policies=[],
                permissions=[],
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
                policies=[],
                permissions=[],
            )
        )
    _attach_policies(grouped, team_id=team_id)
    _attach_permissions(grouped, team_id=team_id)
    return list(grouped.values())


def _attach_policies(
    grouped: dict[int, TeamWithMembersView], team_id: Optional[int]
) -> None:
    if not grouped:
        return
    query = """
        SELECT id, team_id, system_id, name
        FROM policies
        WHERE 1 = 1
    """
    params: list[object] = []
    if team_id is not None:
        query += " AND team_id = ?"
        params.append(team_id)
    query += " ORDER BY id"

    conn = _connect_db()
    try:
        rows = conn.execute(query, tuple(params)).fetchall()
    finally:
        conn.close()

    members_by_system_id = _members_by_system_id(grouped)
    for row in rows:
        row_team_id = int(row["team_id"])
        team = grouped.get(row_team_id)
        if team is None:
            continue
        policy_name = str(row["name"])
        team.policies.append(policy_name)
        system_id_value = row["system_id"]
        if system_id_value is None:
            continue
        member = members_by_system_id.get(int(system_id_value))
        if member is None:
            continue
        member.policies.append(policy_name)

    for team in grouped.values():
        team_policy_values = sorted(set(team.policies))
        team.policies.clear()
        team.policies.extend(team_policy_values)
        for member in team.members:
            member_policy_values = sorted(set(member.policies))
            member.policies.clear()
            member.policies.extend(member_policy_values)


def _attach_permissions(
    grouped: dict[int, TeamWithMembersView], team_id: Optional[int]
) -> None:
    if not grouped:
        return
    enforcer = get_enforcer()
    policies = enforcer.get_policy()
    members_by_system_id = _members_by_system_id(grouped)
    for policy in policies:
        if len(policy) < 4 or policy[3] != "allow":
            continue
        resource = policy[2]
        permission = _strip_skill_prefix(resource)
        subject = policy[0]
        if subject.startswith("team:"):
            try:
                subject_team_id = int(subject.split(":", 1)[1])
            except ValueError:
                continue
            if team_id is not None and subject_team_id != team_id:
                continue
            team = grouped.get(subject_team_id)
            if team is not None:
                team.permissions.append(permission)
            continue
        if subject.startswith("system:"):
            try:
                subject_system_id = int(subject.split(":", 1)[1])
            except ValueError:
                continue
            member = members_by_system_id.get(subject_system_id)
            if member is not None:
                member.permissions.append(permission)
    for team in grouped.values():
        team_permission_values = sorted(set(team.permissions))
        team.permissions.clear()
        team.permissions.extend(team_permission_values)
        for member in team.members:
            member_permission_values = sorted(set(member.permissions))
            member.permissions.clear()
            member.permissions.extend(member_permission_values)


def _members_by_system_id(
    grouped: dict[int, TeamWithMembersView],
) -> dict[int, TeamMemberView]:
    members: dict[int, TeamMemberView] = {}
    for team in grouped.values():
        for member in team.members:
            members[member.id] = member
    return members


def _strip_skill_prefix(resource: str) -> str:
    if resource.startswith("skill:"):
        return resource[len("skill:") :]
    return resource
