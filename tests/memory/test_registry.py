from dataclasses import dataclass

import pytest

from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryListResult,
    MemoryQuery,
    MemoryScope,
)
from src.cyberagent.memory.registry import StaticScopeRegistry


@dataclass
class DummyStore:
    name: str

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        raise NotImplementedError

    def get(
        self, entry_id: str, scope: MemoryScope, namespace: str
    ) -> MemoryEntry | None:
        raise NotImplementedError

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        raise NotImplementedError

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        raise NotImplementedError

    def query(self, query: MemoryQuery) -> MemoryListResult:
        raise NotImplementedError

    def list(
        self, scope: MemoryScope, namespace: str, limit: int, cursor: str | None
    ) -> MemoryListResult:
        raise NotImplementedError


def test_static_scope_registry_routes_stores() -> None:
    agent_store = DummyStore(name="agent")
    team_store = DummyStore(name="team")
    global_store = DummyStore(name="global")
    registry = StaticScopeRegistry(
        agent_store=agent_store,
        team_store=team_store,
        global_store=global_store,
    )
    assert registry.resolve(MemoryScope.AGENT) is agent_store
    assert registry.resolve(MemoryScope.TEAM) is team_store
    assert registry.resolve(MemoryScope.GLOBAL) is global_store


def test_static_scope_registry_requires_store() -> None:
    agent_store = DummyStore(name="agent")
    registry = StaticScopeRegistry(
        agent_store=agent_store, team_store=None, global_store=None
    )
    with pytest.raises(ValueError):
        registry.resolve(MemoryScope.TEAM)
    with pytest.raises(ValueError):
        registry.resolve(MemoryScope.GLOBAL)
