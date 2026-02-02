"""
RBAC enforcer helpers for namespace-scoped tool permissions.
"""

from __future__ import annotations

import os
import logging

import casbin
import casbin_sqlalchemy_adapter

logger = logging.getLogger(__name__)

# Global enforcer instance that will be reused
_global_enforcer = None


def get_enforcer():
    """Get or create the global Casbin enforcer."""
    global _global_enforcer
    if _global_enforcer is None:
        _global_enforcer = _create_enforcer()
    return _global_enforcer


def _create_enforcer():
    """Create a new enforcer instance with domain support enabled."""
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)

    db_path = os.path.join(data_dir, "rbac.db")
    adapter = casbin_sqlalchemy_adapter.Adapter(f"sqlite:///{db_path}")
    model_path = os.path.join(os.path.dirname(__file__), "model.conf")
    enforcer = casbin.Enforcer(model_path, adapter)

    return enforcer


def check_permission(system_id: str, tool_name: str, action_name: str) -> bool:
    """
    Check if a system has permission to perform an action with namespace isolation.

    Args:
        system_id: Requesting system ID (format: namespace_type_name)
        tool_name: Tool being used
        action_name: Target system ID, system type, * or other.
    """
    enforcer = get_enforcer()
    requesting_namespace = get_namespace(system_id)

    if "_" in action_name and action_name.count("_") >= 2:
        roles = enforcer.get_roles_for_user_in_domain(
            action_name, get_namespace(action_name)
        )
        for role in roles:
            if enforcer.enforce(system_id, requesting_namespace, tool_name, role):
                return True
    return enforcer.enforce(system_id, requesting_namespace, tool_name, action_name)


def check_tool_permission(agent_id: str, tool_name: str) -> bool:
    """
    Check if an agent has permission to use a tool by name.
    """
    try:
        enforcer = get_enforcer()
        return enforcer.enforce(agent_id, tool_name, "allow")
    except Exception as exc:
        logger.error("RBAC check failed: %s", exc)
        return False


def get_allowed_actions(system_id: str, tool_name: str) -> list[str]:
    enforcer = get_enforcer()
    namespace = get_namespace(system_id)
    implicit_permissions_for_user = enforcer.get_implicit_permissions_for_user(
        system_id, namespace
    )
    actions = [
        permission[3]
        for permission in implicit_permissions_for_user
        if permission[2] == tool_name
    ]
    cleaned_for_mentioned_roles: list[str] = []
    all_roles = enforcer.get_all_roles_by_domain(namespace)
    if "*" in actions:
        for role in all_roles:
            cleaned_for_mentioned_roles.extend(
                enforcer.get_users_for_role_in_domain(role, namespace)
            )
    else:
        for action in actions:
            if action in all_roles:
                cleaned_for_mentioned_roles.extend(
                    enforcer.get_users_for_role_in_domain(action, namespace)
                )
            else:
                cleaned_for_mentioned_roles.append(action)
    return cleaned_for_mentioned_roles


def get_namespace(system_id: str) -> str:
    if "/" in system_id:
        parts = system_id.split("/")
        if len(parts) == 2:
            return parts[0]

    parts = system_id.split("_")
    if len(parts) != 3:
        raise ValueError(
            "Invalid system ID format, must contain exactly two underscores"
        )
    return parts[0]


def extract_namespace_from_system_id(system_id: str) -> str:
    """Extract namespace from system ID (alias for get_namespace)."""
    return get_namespace(system_id)


def is_namespace(parameter: str) -> bool:
    enforcer = get_enforcer()
    roles = enforcer.get_all_roles_by_domain(parameter)
    return len(roles) > 0


def get_system_id_from_namespace_with_type(
    namespace: str, system_type: str
) -> str | None:
    enforcer = get_enforcer()
    system_ids = enforcer.get_users_for_role_in_domain(system_type, namespace)
    if len(system_ids) == 1:
        return system_ids[0]
    return None


def delete_system_id(system_id: str):
    enforcer = get_enforcer()
    return enforcer.delete_user(system_id)


def create_user(system_type: str, system_id: str):
    enforcer = get_enforcer()
    namespace = get_namespace(system_id)
    return enforcer.add_role_for_user_in_domain(system_id, system_type, namespace)


def give_user_tool_permission(system_id: str, tool_name: str, parameter: str):
    namespace = get_namespace(system_id)
    enforcer = get_enforcer()
    return enforcer.add_policy(system_id, namespace, tool_name, parameter)


def get_tools_names(system_id: str) -> set[str]:
    enforcer = get_enforcer()
    permissions = enforcer.get_implicit_permissions_for_user(
        system_id, get_namespace(system_id)
    )
    tools = [permission[2] for permission in permissions]
    return set(tools)
