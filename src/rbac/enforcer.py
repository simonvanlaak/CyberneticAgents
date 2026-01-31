import os

import casbin
import casbin_sqlalchemy_adapter

# Global enforcer instance that will be reused
_global_enforcer = None


def get_enforcer():
    global _global_enforcer
    if _global_enforcer is None:
        _global_enforcer = _create_enforcer()
    return _global_enforcer


def _create_enforcer():
    """Create a new enforcer instance with domain support enabled."""
    # Ensure data directory exists

    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)

    # Use absolute path for database
    db_path = os.path.join(data_dir, "rbac.db")
    print(f"Enforcer created new db at: {db_path}")
    adapter = casbin_sqlalchemy_adapter.Adapter(f"sqlite:///{db_path}")
    model_path = os.path.join(os.path.dirname(__file__), "model.conf")
    enforcer = casbin.Enforcer(model_path, adapter)

    return enforcer


def check_permission(system_id: str, tool_name: str, action_name: str):
    """
    Check if a system has permission to perform an action with proper namespace isolation.

    Args:
        system_id: Requesting system ID (format: namespace_type_name)
        tool_name: Tool being used
        action_name: Target system ID, system type, * or other.

    Returns:
        True if permission is granted, False otherwise
    """
    enforcer = get_enforcer()
    requesting_namespace = get_namespace(system_id)

    # Handle full system ID format (namespace_type_name)
    if "_" in action_name and action_name.count("_") >= 2:
        # Get target system's roles - Casbin handles namespace isolation via role hierarchy
        roles = enforcer.get_roles_for_user_in_domain(
            action_name, get_namespace(action_name)
        )
        # Check each role for permission
        for role in roles:
            if enforcer.enforce(system_id, requesting_namespace, tool_name, role):
                return True
    return enforcer.enforce(system_id, requesting_namespace, tool_name, action_name)


def get_allowed_actions(system_id: str, tool_name: str):
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
    cleaned_for_mentioned_roles = []
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


def get_namespace(system_id: str):
    # Handle AutoGen Core format "Type/key" by converting to RBAC format
    if "/" in system_id:
        # Convert "Type/key" to a namespace for compatibility
        parts = system_id.split("/")
        if len(parts) == 2:
            return parts[0]

    # Handle original RBAC format "namespace_type_name"
    parts = system_id.split("_")
    if len(parts) != 3:
        raise ValueError(
            "Invalid system ID format, must contain exactly two underscores"
        )
    return parts[0]


def extract_namespace_from_system_id(system_id: str):
    """Extract namespace from system ID (alias for get_namespace)."""
    return get_namespace(system_id)


def is_namespace(parameter: str):
    # check if parameter is a domain
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


def get_tools_names(system_id: str):
    enforcer = get_enforcer()
    permissions = enforcer.get_implicit_permissions_for_user(
        system_id, get_namespace(system_id)
    )
    tools = [permission[2] for permission in permissions]
    return set(list(tools))
