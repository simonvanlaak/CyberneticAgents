import datetime

import pytest

from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryCreateRequest,
    MemoryCrudService,
    MemoryReadRequest,
)
from src.cyberagent.memory.models import (
    MemoryEntry,
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
        self.last_list_owner: str | None = None

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
        self.last_list_owner = owner_agent_id
        items = list(self.entries.values())[:limit]
        return MemoryListResult(items=items, next_cursor=None, has_more=False)


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def _control_actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys3",
        system_id=3,
        team_id=1,
        system_type=SystemType.CONTROL,
    )


def _intelligence_actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys4",
        system_id=4,
        team_id=1,
        system_type=SystemType.INTELLIGENCE,
    )


def test_create_defaults_to_agent_scope_and_owner() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(
        registry=StaticScopeRegistry(store, store, store),
    )
    created = service.create_entries(
        actor=_actor(),
        requests=[
            MemoryCreateRequest(
                content="hello",
                namespace="root",
                scope=None,
                tags=None,
                priority=MemoryPriority.MEDIUM,
                source=MemorySource.MANUAL,
                confidence=0.9,
                expires_at=None,
            )
        ],
    )
    assert created[0].scope == MemoryScope.AGENT
    assert created[0].owner_agent_id == "root_sys1"


def test_agent_scope_defaults_namespace_when_missing() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    created = service.create_entries(
        actor=_actor(),
        requests=[
            MemoryCreateRequest(
                content="hello",
                namespace=None,
                scope=MemoryScope.AGENT,
                tags=None,
                priority=MemoryPriority.MEDIUM,
                source=MemorySource.MANUAL,
                confidence=0.9,
                expires_at=None,
            )
        ],
    )
    assert created[0].namespace == "root_sys1"


def test_team_scope_requires_namespace() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    with pytest.raises(ValueError):
        service.create_entries(
            actor=_control_actor(),
            requests=[
                MemoryCreateRequest(
                    content="team",
                    namespace=None,
                    scope=MemoryScope.TEAM,
                    tags=None,
                    priority=MemoryPriority.MEDIUM,
                    source=MemorySource.MANUAL,
                    confidence=0.9,
                    expires_at=None,
                    target_team_id=1,
                )
            ],
        )


def test_global_scope_requires_namespace() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    with pytest.raises(ValueError):
        service.create_entries(
            actor=_intelligence_actor(),
            requests=[
                MemoryCreateRequest(
                    content="global",
                    namespace=None,
                    scope=MemoryScope.GLOBAL,
                    tags=None,
                    priority=MemoryPriority.MEDIUM,
                    source=MemorySource.MANUAL,
                    confidence=0.9,
                    expires_at=None,
                )
            ],
        )


def test_team_scope_requires_layer() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    with pytest.raises(ValueError):
        service.create_entries(
            actor=_control_actor(),
            requests=[
                MemoryCreateRequest(
                    content="team",
                    namespace="team",
                    scope=MemoryScope.TEAM,
                    tags=None,
                    priority=MemoryPriority.MEDIUM,
                    source=MemorySource.MANUAL,
                    confidence=0.9,
                    expires_at=None,
                    target_team_id=1,
                    layer=None,
                )
            ],
        )


def test_global_scope_requires_layer() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    with pytest.raises(ValueError):
        service.create_entries(
            actor=_intelligence_actor(),
            requests=[
                MemoryCreateRequest(
                    content="global",
                    namespace="user",
                    scope=MemoryScope.GLOBAL,
                    tags=None,
                    priority=MemoryPriority.MEDIUM,
                    source=MemorySource.MANUAL,
                    confidence=0.9,
                    expires_at=None,
                    layer=None,
                )
            ],
        )


def test_create_enforces_bulk_limit() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    requests = [
        MemoryCreateRequest(
            content=f"item-{idx}",
            namespace="root",
            scope=MemoryScope.AGENT,
            tags=None,
            priority=MemoryPriority.MEDIUM,
            source=MemorySource.MANUAL,
            confidence=0.9,
            expires_at=None,
        )
        for idx in range(11)
    ]
    with pytest.raises(ValueError):
        service.create_entries(actor=_actor(), requests=requests)


def test_list_defaults_scope_and_passes_owner() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    service.list_entries(
        actor=_actor(),
        scope=None,
        namespace="root",
        limit=10,
        cursor=None,
    )
    assert store.last_list_owner == "root_sys1"


def test_team_scope_write_requires_sys3_or_higher() -> None:
    store = InMemoryStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    with pytest.raises(PermissionError):
        service.create_entries(
            actor=_actor(),
            requests=[
                MemoryCreateRequest(
                    content="team",
                    namespace="root",
                    scope=MemoryScope.TEAM,
                    tags=None,
                    priority=MemoryPriority.MEDIUM,
                    source=MemorySource.MANUAL,
                    confidence=0.9,
                    expires_at=None,
                    target_team_id=1,
                )
            ],
        )


def test_read_blocks_non_owner_for_agent_scope() -> None:
    store = InMemoryStore()
    now = datetime.datetime.now(datetime.timezone.utc)
    store.add(
        MemoryEntry(
            id="mem-1",
            scope=MemoryScope.AGENT,
            namespace="root",
            owner_agent_id="other_agent",
            content="secret",
            priority=MemoryPriority.MEDIUM,
            created_at=now,
            updated_at=now,
            source=MemorySource.MANUAL,
            confidence=0.5,
        )
    )
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    with pytest.raises(PermissionError):
        service.read_entry(
            actor=_actor(),
            request=MemoryReadRequest(
                entry_id="mem-1",
                scope=MemoryScope.AGENT,
                namespace="root",
            ),
        )
