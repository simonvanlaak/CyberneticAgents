"""Team lookup helpers and skill envelope permissions."""

from __future__ import annotations

from src.cyberagent.authz import (
    allow_skill_for_team,
    list_team_allowed_skills,
    revoke_skill_for_team,
    revoke_system_grants_for_team_skill,
)
from src.cyberagent.db.models.team import Team, get_team as _get_team
from src.cyberagent.services.audit import log_event


def get_team(team_id: int) -> Team | None:
    """Return a team by id."""
    return _get_team(team_id)


def list_allowed_skills(team_id: int) -> list[str]:
    """List all skills allowed by a team's envelope."""
    return list_team_allowed_skills(team_id)


def add_allowed_skill(team_id: int, skill_name: str, actor_id: str) -> bool:
    """Allow a skill within a team's envelope."""
    added = allow_skill_for_team(team_id, skill_name)
    log_event(
        "skill_envelope_add",
        service="teams",
        team_id=team_id,
        skill_name=skill_name,
        actor_id=actor_id,
        added=added,
    )
    return added


def remove_allowed_skill(team_id: int, skill_name: str, actor_id: str) -> int:
    """Remove a skill from a team's envelope and cascade revokes."""
    revoked_grants = revoke_system_grants_for_team_skill(team_id, skill_name)
    removed = revoke_skill_for_team(team_id, skill_name)
    log_event(
        "skill_envelope_remove",
        service="teams",
        team_id=team_id,
        skill_name=skill_name,
        actor_id=actor_id,
        removed=removed,
        revoked_grants=revoked_grants,
    )
    return revoked_grants


def set_allowed_skills(team_id: int, skill_names: list[str], actor_id: str) -> None:
    """Replace a team's envelope with the provided skills."""
    current = set(list_allowed_skills(team_id))
    desired = set(skill_names)

    for skill_name in current - desired:
        remove_allowed_skill(team_id, skill_name, actor_id)

    for skill_name in desired - current:
        add_allowed_skill(team_id, skill_name, actor_id)

    log_event(
        "skill_envelope_set",
        service="teams",
        team_id=team_id,
        actor_id=actor_id,
        skill_count=len(skill_names),
    )
