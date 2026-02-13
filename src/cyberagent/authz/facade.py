"""Authorization facade for cyberagent domain modules.

This module hides direct Casbin enforcer access behind domain-oriented helpers.
"""

from __future__ import annotations

from collections.abc import Iterable

import casbin

from src.rbac import enforcer as tools_rbac_enforcer
from src.rbac import skill_permissions_enforcer


def ensure_policy_bootstrap_state() -> None:
    """Ensure both authorization policy stores are initialized."""
    tools_rbac_enforcer.get_enforcer()
    skill_permissions_enforcer.get_enforcer()


def has_tool_permission(agent_id: str, tool_name: str) -> bool:
    """Return whether an agent can execute a tool."""
    return bool(tools_rbac_enforcer.check_tool_permission(agent_id, tool_name))


def grant_tool_permission(agent_id: str, tool_name: str, action_name: str) -> bool:
    """Grant a tool permission to an agent identifier."""
    return bool(
        tools_rbac_enforcer.give_user_tool_permission(
            agent_id,
            tool_name,
            action_name,
        )
    )


def list_team_allowed_skills(team_id: int) -> list[str]:
    """List skills allowed by a team's skill envelope."""
    policies = _skill_enforcer().get_filtered_policy(0, _team_subject(team_id))
    return _sorted_unique_skills(policies)


def list_system_granted_skills(system_id: int) -> list[str]:
    """List skills granted directly to a system."""
    policies = _skill_enforcer().get_filtered_policy(0, _system_subject(system_id))
    return _sorted_unique_skills(policies)


def allow_skill_for_team(team_id: int, skill_name: str) -> bool:
    """Allow a skill in a team's envelope."""
    enforcer = _skill_enforcer()
    added = enforcer.add_policy(
        _team_subject(team_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
    if added:
        enforcer.save_policy()
    return bool(added)


def revoke_skill_for_team(team_id: int, skill_name: str) -> bool:
    """Revoke a skill from a team's envelope."""
    enforcer = _skill_enforcer()
    removed = enforcer.remove_policy(
        _team_subject(team_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
    if removed:
        enforcer.save_policy()
    return bool(removed)


def grant_skill_to_system(system_id: int, team_id: int, skill_name: str) -> bool:
    """Grant a skill directly to a system."""
    enforcer = _skill_enforcer()
    added = enforcer.add_policy(
        _system_subject(system_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
    if added:
        enforcer.save_policy()
    return bool(added)


def revoke_skill_from_system(system_id: int, team_id: int, skill_name: str) -> bool:
    """Revoke a skill grant from a system."""
    enforcer = _skill_enforcer()
    removed = enforcer.remove_policy(
        _system_subject(system_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
    if removed:
        enforcer.save_policy()
    return bool(removed)


def revoke_system_grants_for_team_skill(team_id: int, skill_name: str) -> int:
    """Revoke all system grants for a team/skill combination.

    Returns:
        Number of system policies removed.
    """
    enforcer = _skill_enforcer()
    policies = enforcer.get_filtered_policy(
        1,
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )

    removed = 0
    for policy in policies:
        if not policy or not policy[0].startswith("system:"):
            continue
        if enforcer.remove_policy(*policy):
            removed += 1

    if removed:
        enforcer.save_policy()
    return removed


def is_team_skill_allowed(team_id: int, skill_name: str) -> bool:
    """Return whether a team's envelope allows a skill."""
    return bool(
        _skill_enforcer().enforce(
            _team_subject(team_id),
            str(team_id),
            _skill_resource(skill_name),
            "allow",
        )
    )


def is_system_skill_granted(system_id: int, team_id: int, skill_name: str) -> bool:
    """Return whether a system has a direct grant for a skill."""
    return bool(
        _skill_enforcer().enforce(
            _system_subject(system_id),
            str(team_id),
            _skill_resource(skill_name),
            "allow",
        )
    )


def reload_skill_policy_store() -> None:
    """Reload skill policies from persistent storage."""
    _skill_enforcer().load_policy()


def _skill_enforcer() -> casbin.Enforcer:
    ensure_policy_bootstrap_state()
    return skill_permissions_enforcer.get_enforcer()


def _team_subject(team_id: int) -> str:
    return f"team:{team_id}"


def _system_subject(system_id: int) -> str:
    return f"system:{system_id}"


def _skill_resource(skill_name: str) -> str:
    return f"skill:{skill_name}"


def _sorted_unique_skills(policies: Iterable[list[str]]) -> list[str]:
    skills = {
        _strip_skill_prefix(policy[2])
        for policy in policies
        if len(policy) >= 4 and policy[3] == "allow"
    }
    return sorted(skills)


def _strip_skill_prefix(resource: str) -> str:
    if resource.startswith("skill:"):
        return resource[len("skill:") :]
    return resource
