import datetime

import pytest

from src.cyberagent.memory.crud import MemoryActorContext, MemoryCrudService
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryListResult,
    MemoryPriority,
    MemoryQuery,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.cyberagent.memory.store import MemoryStore
from src.enums import SystemType


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.entries: dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self.entries[entry.id] = entry
        return entry

    def get(
        self, entry_id: str, scope: MemoryScope, namespace: str
    ) -> MemoryEntry | None:
        return self.entries.get(entry_id)

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        self.entries[entry.id] = entry
        return entry

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        return self.entries.pop(entry_id, None) is not None

    def query(self, query: MemoryQuery) -> MemoryListResult:
        raise NotImplementedError

    def list(
        self,
        scope: MemoryScope,
        namespace: str,
        limit: int,
        cursor: str | None,
        owner_agent_id: str | None = None,
    ) -> MemoryListResult:
        raise NotImplementedError


def _actor(system_type: SystemType) -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=system_type,
    )


def _entry(content: str) -> MemoryEntry:
    now = datetime.datetime.now(datetime.timezone.utc)
    return MemoryEntry(
        id="mem-1",
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=content,
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        source=MemorySource.MANUAL,
        confidence=0.9,
        layer=MemoryLayer.SESSION,
    )


def test_promote_requires_team_write_permission() -> None:
    agent_store = InMemoryStore()
    team_store = InMemoryStore()
    registry = StaticScopeRegistry(agent_store, team_store, team_store)
    service = MemoryCrudService(registry=registry)
    agent_store.add(_entry("agent-content"))
    with pytest.raises(PermissionError):
        service.promote_entry(
            actor=_actor(SystemType.OPERATION),
            entry_id="mem-1",
            source_scope=MemoryScope.AGENT,
            target_scope=MemoryScope.TEAM,
            namespace="root",
        )


def test_promote_creates_conflict_entry() -> None:
    agent_store = InMemoryStore()
    team_store = InMemoryStore()
    registry = StaticScopeRegistry(agent_store, team_store, team_store)
    service = MemoryCrudService(registry=registry)
    agent_store.add(_entry("agent-content"))
    team_store.add(
        MemoryEntry(
            id="mem-1",
            scope=MemoryScope.TEAM,
            namespace="root",
            owner_agent_id="root_sys1",
            content="different",
            priority=MemoryPriority.MEDIUM,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            source=MemorySource.MANUAL,
            confidence=0.9,
            layer=MemoryLayer.SESSION,
        )
    )
    promoted = service.promote_entry(
        actor=_actor(SystemType.CONTROL),
        entry_id="mem-1",
        source_scope=MemoryScope.AGENT,
        target_scope=MemoryScope.TEAM,
        namespace="root",
    )
    assert promoted.conflict is True
    assert promoted.conflict_of == "mem-1"
    assert promoted.id != "mem-1"
