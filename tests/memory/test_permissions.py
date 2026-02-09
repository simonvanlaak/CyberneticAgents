from src.cyberagent.memory.models import MemoryScope
from src.cyberagent.memory.permissions import (
    MemoryAction,
    check_memory_permission,
)
from src.enums import SystemType


def test_team_scope_read_allowed_for_sys1_sys2() -> None:
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=1,
            system_type=SystemType.OPERATION,
            scope=MemoryScope.TEAM,
            action=MemoryAction.READ,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=1,
            system_type=SystemType.COORDINATION_2,
            scope=MemoryScope.TEAM,
            action=MemoryAction.READ,
        )
        is True
    )


def test_team_scope_write_requires_sys3_or_higher() -> None:
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=1,
            system_type=SystemType.CONTROL,
            scope=MemoryScope.TEAM,
            action=MemoryAction.WRITE,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=1,
            system_type=SystemType.POLICY,
            scope=MemoryScope.TEAM,
            action=MemoryAction.WRITE,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=1,
            system_type=SystemType.OPERATION,
            scope=MemoryScope.TEAM,
            action=MemoryAction.WRITE,
        )
        is False
    )


def test_team_scope_blocks_cross_team_access() -> None:
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=2,
            system_type=SystemType.CONTROL,
            scope=MemoryScope.TEAM,
            action=MemoryAction.WRITE,
        )
        is False
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=2,
            system_type=SystemType.OPERATION,
            scope=MemoryScope.TEAM,
            action=MemoryAction.READ,
        )
        is False
    )


def test_global_scope_read_allowed_for_all_system_types() -> None:
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=None,
            system_type=SystemType.INTELLIGENCE,
            scope=MemoryScope.GLOBAL,
            action=MemoryAction.READ,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=None,
            system_type=SystemType.CONTROL,
            scope=MemoryScope.GLOBAL,
            action=MemoryAction.READ,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=None,
            system_type=SystemType.OPERATION,
            scope=MemoryScope.GLOBAL,
            action=MemoryAction.READ,
        )
        is True
    )


def test_global_scope_write_requires_sys4() -> None:
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=None,
            system_type=SystemType.INTELLIGENCE,
            scope=MemoryScope.GLOBAL,
            action=MemoryAction.WRITE,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=None,
            system_type=SystemType.POLICY,
            scope=MemoryScope.GLOBAL,
            action=MemoryAction.WRITE,
        )
        is False
    )


def test_agent_scope_allows_owner_only() -> None:
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=1,
            system_type=SystemType.OPERATION,
            scope=MemoryScope.AGENT,
            action=MemoryAction.READ,
        )
        is True
    )
    assert (
        check_memory_permission(
            actor_team_id=1,
            target_team_id=2,
            system_type=SystemType.OPERATION,
            scope=MemoryScope.AGENT,
            action=MemoryAction.READ,
        )
        is False
    )
