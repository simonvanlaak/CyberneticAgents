"""Memory scope permission checks."""

from __future__ import annotations

from enum import Enum

from src.cyberagent.memory.models import MemoryScope
from src.enums import SystemType


class MemoryAction(str, Enum):
    READ = "read"
    WRITE = "write"


def check_memory_permission(
    *,
    actor_team_id: int,
    target_team_id: int | None,
    system_type: SystemType,
    scope: MemoryScope,
    action: MemoryAction,
) -> bool:
    """
    Evaluate memory permission rules for a given scope and action.

    Args:
        actor_team_id: Team ID for the acting system.
        target_team_id: Target team ID for team/agent scopes.
        system_type: Actor system type (Sys1..Sys5).
        scope: Memory scope to access.
        action: Read or write access.

    Returns:
        True if allowed, False otherwise.
    """
    if scope == MemoryScope.GLOBAL:
        return system_type == SystemType.INTELLIGENCE

    if scope == MemoryScope.TEAM:
        if target_team_id is None or target_team_id != actor_team_id:
            return False
        if action == MemoryAction.READ:
            return True
        return system_type in {
            SystemType.CONTROL,
            SystemType.INTELLIGENCE,
            SystemType.POLICY,
        }

    if scope == MemoryScope.AGENT:
        if target_team_id is None or target_team_id != actor_team_id:
            return False
        return True

    return False
