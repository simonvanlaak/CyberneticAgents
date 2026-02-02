"""Team lookup helpers and skill envelope permissions."""

from __future__ import annotations

from typing import Iterable

import casbin

from src.cyberagent.db.models.team import Team, get_team as _get_team
from src.cyberagent.services.audit import log_event
from src.rbac.skill_permissions_enforcer import get_enforcer


def get_team(team_id: int) -> Team | None:
    """Return a team by id."""
    return _get_team(team_id)


def list_allowed_skills(team_id: int) -> list[str]:
    """
    List all skills allowed by a team's envelope.

    Args:
        team_id: Team identifier.

    Returns:
        Sorted list of allowed skill names.
    """
    enforcer = get_enforcer()
    policies = enforcer.get_filtered_policy(0, _team_subject(team_id))
    skills = [
        _strip_skill_prefix(policy[2])
        for policy in policies
        if len(policy) >= 4 and policy[3] == "allow"
    ]
    return sorted(set(skills))


def add_allowed_skill(team_id: int, skill_name: str, actor_id: str) -> bool:
    """
    Allow a skill within a team's envelope.

    Args:
        team_id: Team identifier.
        skill_name: Skill name to allow.
        actor_id: Actor performing the mutation (audit only).

    Returns:
        True if the policy was added, False if it already existed.
    """
    enforcer = get_enforcer()
    added = enforcer.add_policy(
        _team_subject(team_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
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
    """
    Remove a skill from a team's envelope and cascade revokes.

    Args:
        team_id: Team identifier.
        skill_name: Skill name to remove.
        actor_id: Actor performing the mutation (audit only).

    Returns:
        Number of system grants revoked within the team.
    """
    enforcer = get_enforcer()
    skill_resource = _skill_resource(skill_name)
    team_id_str = str(team_id)

    revoked_grants = _revoke_system_grants(
        enforcer.get_filtered_policy(1, team_id_str, skill_resource, "allow"),
        enforcer,
    )

    removed = enforcer.remove_policy(
        _team_subject(team_id),
        team_id_str,
        skill_resource,
        "allow",
    )
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
    """
    Replace a team's envelope with the provided skills.

    Args:
        team_id: Team identifier.
        skill_names: List of skill names to allow.
        actor_id: Actor performing the mutation (audit only).
    """
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


def _team_subject(team_id: int) -> str:
    return f"team:{team_id}"


def _skill_resource(skill_name: str) -> str:
    return f"skill:{skill_name}"


def _strip_skill_prefix(resource: str) -> str:
    if resource.startswith("skill:"):
        return resource[len("skill:") :]
    return resource


def _revoke_system_grants(
    policies: Iterable[list[str]], enforcer: casbin.Enforcer
) -> int:
    revoked = 0
    for policy in policies:
        if policy and policy[0].startswith("system:"):
            if enforcer.remove_policy(*policy):
                revoked += 1
    return revoked
