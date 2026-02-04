import datetime

import pytest
from autogen_core import AgentId, CancellationToken

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
from src.cyberagent.tools.memory_crud import (
    MemoryCrudArgs,
    MemoryCrudTool,
)
from src.enums import SystemType


class InMemoryCursorStore(MemoryStore):
    def __init__(self) -> None:
        self.entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self.entries.append(entry)
        return entry

    def get(
        self, entry_id: str, scope: MemoryScope, namespace: str
    ) -> MemoryEntry | None:
        for entry in self.entries:
            if (
                entry.id == entry_id
                and entry.scope == scope
                and entry.namespace == namespace
            ):
                return entry
        return None

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        for idx, existing in enumerate(self.entries):
            if existing.id == entry.id:
                self.entries[idx] = entry
                break
        return entry

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        for idx, entry in enumerate(self.entries):
            if (
                entry.id == entry_id
                and entry.scope == scope
                and entry.namespace == namespace
            ):
                self.entries.pop(idx)
                return True
        return False

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
        filtered = [
            entry
            for entry in self.entries
            if entry.scope == scope
            and entry.namespace == namespace
            and (owner_agent_id is None or entry.owner_agent_id == owner_agent_id)
        ]
        offset = 0
        if cursor:
            if not cursor.startswith("offset:"):
                raise ValueError("Invalid cursor format.")
            offset = int(cursor[len("offset:") :])
        end = offset + limit
        items = filtered[offset:end]
        has_more = end < len(filtered)
        next_cursor = f"offset:{end}" if has_more else None
        return MemoryListResult(items=items, next_cursor=next_cursor, has_more=has_more)


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def _tool(store: MemoryStore) -> MemoryCrudTool:
    registry = StaticScopeRegistry(store, store, store)
    service = MemoryCrudService(registry=registry)
    return MemoryCrudTool(
        agent_id=AgentId.from_str("System1/root"),
        service=service,
        actor_context=_actor(),
    )


def _entry(entry_id: str, content: str) -> MemoryEntry:
    now = datetime.datetime.now(datetime.timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=content,
        tags=[],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.9,
        layer=MemoryLayer.WORKING,
        version=1,
        etag="etag-1",
    )


@pytest.mark.asyncio
async def test_list_returns_cursor_and_has_more() -> None:
    store = InMemoryCursorStore()
    store.add(_entry("mem-1", "first"))
    store.add(_entry("mem-2", "second"))
    store.add(_entry("mem-3", "third"))
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(action="list", namespace="root", limit=2),
        CancellationToken(),
    )
    assert response.errors == []
    assert response.has_more is True
    assert response.next_cursor == "offset:2"
    assert [item["id"] for item in response.items] == ["mem-1", "mem-2"]


@pytest.mark.asyncio
async def test_list_invalid_cursor_returns_invalid_params() -> None:
    store = InMemoryCursorStore()
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(action="list", namespace="root", cursor="bad"),
        CancellationToken(),
    )
    assert response.items == []
    assert response.has_more is False
    assert response.next_cursor is None
    assert response.errors
    assert response.errors[0].code == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_update_if_match_mismatch_creates_conflict() -> None:
    store = InMemoryCursorStore()
    store.add(_entry("mem-1", "original"))
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(
            action="update",
            namespace="root",
            items=[
                {
                    "entry_id": "mem-1",
                    "content": "new",
                    "if_match": "etag-2",
                }
            ],
        ),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "CONFLICT"
    conflicts = [entry for entry in store.entries if entry.is_conflict]
    assert len(conflicts) == 1
    assert conflicts[0].conflict_of == "mem-1"
    assert conflicts[0].content == "new"
    original = store.get("mem-1", MemoryScope.AGENT, "root")
    assert original is not None
    assert original.content == "original"


@pytest.mark.asyncio
async def test_bulk_limit_exceeded_returns_invalid_params() -> None:
    store = InMemoryCursorStore()
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(
            action="create",
            namespace="root",
            items=[
                {
                    "content": f"item-{idx}",
                    "priority": "medium",
                    "source": "manual",
                    "confidence": 0.5,
                }
                for idx in range(11)
            ],
        ),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "INVALID_PARAMS"
    assert store.entries == []
