from __future__ import annotations

from pathlib import Path

from typing import cast

import pytest

from src.rbac import enforcer as rbac_enforcer
from src.rbac.system_types import SystemTypes


@pytest.fixture()
def fresh_enforcer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    rbac_enforcer._global_enforcer = None
    enforcer = rbac_enforcer.get_enforcer()
    enforcer.clear_policy()
    yield enforcer
    rbac_enforcer._global_enforcer = None


def test_get_namespace_formats() -> None:
    assert rbac_enforcer.get_namespace("UserAgent/root") == "UserAgent"
    assert rbac_enforcer.get_namespace("alpha_control_sys3") == "alpha"

    with pytest.raises(ValueError, match="Invalid system ID format"):
        rbac_enforcer.get_namespace("badformat")


def test_check_permission_full_system_id_uses_roles(fresh_enforcer) -> None:
    requester = "alpha_control_sys3"
    target = "alpha_ops_sys1"
    tool_name = "delegate"
    namespace = "alpha"
    role = "ops_role"

    fresh_enforcer.add_role_for_user_in_domain(requester, role, namespace)
    fresh_enforcer.add_role_for_user_in_domain(target, role, namespace)
    fresh_enforcer.add_policy(role, namespace, tool_name, "*")

    assert rbac_enforcer.check_permission(requester, tool_name, target) is False


def test_get_allowed_actions_and_tools(fresh_enforcer) -> None:
    requester = "alpha_control_sys3"
    target = "alpha_ops_sys1"
    namespace = "alpha"
    role = "ops_role"

    fresh_enforcer.add_role_for_user_in_domain(requester, role, namespace)
    fresh_enforcer.add_role_for_user_in_domain(target, role, namespace)
    fresh_enforcer.add_policy(role, namespace, "delegate", "*")
    fresh_enforcer.add_policy(role, namespace, "observe", "status")

    allowed = rbac_enforcer.get_allowed_actions(requester, "delegate")
    assert requester in allowed
    assert target in allowed

    tool_names = rbac_enforcer.get_tools_names(requester)
    assert tool_names == {"delegate", "observe"}


def test_namespace_helpers(fresh_enforcer) -> None:
    system_id = "alpha_ops_sys1"
    assert rbac_enforcer.extract_namespace_from_system_id(system_id) == "alpha"

    rbac_enforcer.create_user(SystemTypes.SYSTEM_1_OPERATIONS, system_id)

    assert rbac_enforcer.is_namespace("alpha") is True
    assert (
        rbac_enforcer.get_system_id_from_namespace_with_type(
            "alpha", SystemTypes.SYSTEM_1_OPERATIONS
        )
        == system_id
    )

    delete_result = cast(list[list[str]], rbac_enforcer.delete_system_id(system_id))
    assert delete_result
    assert delete_result[0][0] == system_id
