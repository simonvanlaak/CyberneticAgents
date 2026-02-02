"""System lookup helpers and skill grant permissions."""

from __future__ import annotations

import logging

from src.cyberagent.db.models.system import (
    System,
    get_system as _get_system,
    get_system_by_type as _get_system_by_type,
    get_systems_by_type as _get_systems_by_type,
    ensure_default_systems_for_team as _ensure_default_systems_for_team,
)
from src.enums import SystemType
from src.rbac.skill_permissions_enforcer import get_enforcer
from src.cyberagent.services import recursions as recursions_service
from src.cyberagent.services import teams as teams_service
from src.cyberagent.services.audit import log_event

logger = logging.getLogger(__name__)


def get_system(system_id: int) -> System | None:
    """Return a system by id."""
    return _get_system(system_id)


def get_system_by_type(team_id: int, system_type: SystemType) -> System:
    """Return a system by type for a team."""
    return _get_system_by_type(team_id, system_type)


def get_systems_by_type(team_id: int, system_type: SystemType) -> list[System]:
    """Return systems by type for a team."""
    return _get_systems_by_type(team_id, system_type)


def ensure_default_systems_for_team(team_id: int) -> list[System]:
    """Ensure default systems exist for a team."""
    return _ensure_default_systems_for_team(team_id)


def list_granted_skills(system_id: int) -> list[str]:
    """
    List all skill grants for a system.

    Args:
        system_id: System identifier.

    Returns:
        Sorted list of granted skill names.
    """
    enforcer = get_enforcer()
    policies = enforcer.get_filtered_policy(0, _system_subject(system_id))
    skills = [
        _strip_skill_prefix(policy[2])
        for policy in policies
        if len(policy) >= 4 and policy[3] == "allow"
    ]
    return sorted(set(skills))


def add_skill_grant(system_id: int, skill_name: str, actor_id: str) -> bool:
    """
    Grant a skill to a system.

    Args:
        system_id: System identifier.
        skill_name: Skill name to grant.
        actor_id: Actor performing the mutation (audit only).

    Returns:
        True if the policy was added, False if it already existed.

    Raises:
        PermissionError: If the team envelope blocks the skill or the system limit
            is exceeded.
    """
    team_id = _get_team_id_or_raise(system_id)
    _require_envelope_allows(team_id, system_id, skill_name, actor_id)

    current = list_granted_skills(system_id)
    if skill_name in current:
        return False
    if len(current) >= 5:
        _raise_permission_error(
            team_id, system_id, skill_name, "system_skill_limit", actor_id
        )

    enforcer = get_enforcer()
    added = enforcer.add_policy(
        _system_subject(system_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
    if added:
        enforcer.save_policy()
    log_event(
        "skill_grant_add",
        service="systems",
        team_id=team_id,
        system_id=system_id,
        skill_name=skill_name,
        actor_id=actor_id,
        added=added,
    )
    return added


def remove_skill_grant(system_id: int, skill_name: str, actor_id: str) -> bool:
    """
    Revoke a skill grant from a system.

    Args:
        system_id: System identifier.
        skill_name: Skill name to revoke.
        actor_id: Actor performing the mutation (audit only).

    Returns:
        True if the policy existed and was removed.
    """
    team_id = _get_team_id_or_raise(system_id)
    enforcer = get_enforcer()
    removed = enforcer.remove_policy(
        _system_subject(system_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    )
    log_event(
        "skill_grant_remove",
        service="systems",
        team_id=team_id,
        system_id=system_id,
        skill_name=skill_name,
        actor_id=actor_id,
        removed=removed,
    )
    return removed


def set_skill_grants(system_id: int, skill_names: list[str], actor_id: str) -> None:
    """
    Replace a system's grants with the provided skill list.

    Args:
        system_id: System identifier.
        skill_names: Skills to grant.
        actor_id: Actor performing the mutation (audit only).

    Raises:
        PermissionError: If the team envelope blocks any skill or the limit is exceeded.
    """
    if len(skill_names) > 5:
        _raise_permission_error(
            _get_team_id_or_raise(system_id),
            system_id,
            skill_names[0] if skill_names else "",
            "system_skill_limit",
            actor_id,
        )

    team_id = _get_team_id_or_raise(system_id)
    for skill_name in skill_names:
        _require_envelope_allows(team_id, system_id, skill_name, actor_id)

    current = set(list_granted_skills(system_id))
    desired = set(skill_names)

    for skill_name in current - desired:
        remove_skill_grant(system_id, skill_name, actor_id)

    for skill_name in desired - current:
        add_skill_grant(system_id, skill_name, actor_id)
    log_event(
        "skill_grant_set",
        service="systems",
        team_id=team_id,
        system_id=system_id,
        actor_id=actor_id,
        skill_count=len(skill_names),
    )


def can_execute_skill(system_id: int, skill_name: str) -> tuple[bool, str | None]:
    """
    Evaluate whether a system can execute a skill.

    Args:
        system_id: System identifier.
        skill_name: Skill name to evaluate.

    Returns:
        Tuple of (allowed, deny_category). Deny category is None on allow.
    """
    team_id = _get_team_id_or_raise(system_id)
    enforcer = get_enforcer()

    def _evaluate_permission() -> str | None:
        deny: str | None = None
        if not _is_root_team(team_id):
            if not enforcer.enforce(
                _team_subject(team_id),
                str(team_id),
                _skill_resource(skill_name),
                "allow",
            ):
                deny = "team_envelope"
        if deny is None:
            if not enforcer.enforce(
                _system_subject(system_id),
                str(team_id),
                _skill_resource(skill_name),
                "allow",
            ):
                deny = "system_grant"
        if deny is None:
            if not _check_recursion_chain(team_id, skill_name, enforcer):
                deny = "system_grant"
        return deny

    deny_category = _evaluate_permission()
    if deny_category is not None:
        enforcer.load_policy()
        deny_category = _evaluate_permission()

    allowed = deny_category is None
    log_event(
        "skill_permission_decision",
        service="systems",
        team_id=team_id,
        system_id=system_id,
        skill_name=skill_name,
        allowed=allowed,
        failed_rule_category=deny_category,
    )
    return allowed, deny_category


def _get_team_id_or_raise(system_id: int) -> int:
    system = _get_system(system_id)
    if system is None:
        raise ValueError(f"System id {system_id} is not registered.")
    return system.team_id


def _require_envelope_allows(
    team_id: int, system_id: int, skill_name: str, actor_id: str | None
) -> None:
    if _is_root_team(team_id):
        return
    enforcer = get_enforcer()
    if enforcer.enforce(
        _team_subject(team_id),
        str(team_id),
        _skill_resource(skill_name),
        "allow",
    ):
        return
    _raise_permission_error(team_id, system_id, skill_name, "team_envelope", actor_id)


def _raise_permission_error(
    team_id: int,
    system_id: int,
    skill_name: str,
    category: str,
    actor_id: str | None,
) -> None:
    log_event(
        "skill_permission_denied",
        level=logging.WARNING,
        service="systems",
        team_id=team_id,
        system_id=system_id,
        skill_name=skill_name,
        actor_id=actor_id,
        failed_rule_category=category,
    )
    raise PermissionError(
        "Permission denied for team_id="
        f"{team_id} system_id={system_id} "
        f"skill_name={skill_name} category={category}"
    )


def _team_subject(team_id: int) -> str:
    return f"team:{team_id}"


def _system_subject(system_id: int) -> str:
    return f"system:{system_id}"


def _skill_resource(skill_name: str) -> str:
    return f"skill:{skill_name}"


def _strip_skill_prefix(resource: str) -> str:
    if resource.startswith("skill:"):
        return resource[len("skill:") :]
    return resource


def _is_root_team(team_id: int) -> bool:
    team = teams_service.get_team(team_id)
    return team is not None and team.name == "default_team"


def _check_recursion_chain(team_id: int, skill_name: str, enforcer) -> bool:
    links = recursions_service.get_recursion_chain(team_id)
    if not links:
        return True
    for link in links:
        if not enforcer.enforce(
            _system_subject(link.origin_system_id),
            str(link.parent_team_id),
            _skill_resource(skill_name),
            "allow",
        ):
            return False
    return True
