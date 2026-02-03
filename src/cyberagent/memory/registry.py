"""Scope registry for memory stores."""

from __future__ import annotations

from dataclasses import dataclass

from src.cyberagent.memory.models import MemoryScope
from src.cyberagent.memory.store import MemoryStore


@dataclass(slots=True)
class StaticScopeRegistry:
    """Simple scope registry with fixed stores per scope."""

    agent_store: MemoryStore | None
    team_store: MemoryStore | None
    global_store: MemoryStore | None

    def resolve(self, scope: MemoryScope) -> MemoryStore:
        if scope == MemoryScope.AGENT:
            if self.agent_store is None:
                raise ValueError("agent store is not configured")
            return self.agent_store
        if scope == MemoryScope.TEAM:
            if self.team_store is None:
                raise ValueError("team store is not configured")
            return self.team_store
        if scope == MemoryScope.GLOBAL:
            if self.global_store is None:
                raise ValueError("global store is not configured")
            return self.global_store
        raise ValueError(f"unsupported memory scope: {scope}")
