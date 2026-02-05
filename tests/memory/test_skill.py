import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from autogen_core import AgentId, CancellationToken

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import init_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
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
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.rbac import skill_permissions_enforcer
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
        filtered = [
            entry
            for entry in self.entries
            if entry.scope == query.scope
            and entry.namespace == query.namespace
            and (
                query.owner_agent_id is None
                or entry.owner_agent_id == query.owner_agent_id
            )
            and (query.layer is None or entry.layer == query.layer)
        ]
        offset = 0
        if query.cursor:
            if not query.cursor.startswith("offset:"):
                raise ValueError("Invalid cursor format.")
            offset = int(query.cursor[len("offset:") :])
        end = offset + query.limit
        items = filtered[offset:end]
        has_more = end < len(filtered)
        next_cursor = f"offset:{end}" if has_more else None
        return MemoryListResult(items=items, next_cursor=next_cursor, has_more=has_more)

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


class NotImplementedStore(InMemoryCursorStore):
    def update(self, entry: MemoryEntry) -> MemoryEntry:
        raise NotImplementedError("Updates are not supported.")

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        raise NotImplementedError("Deletes are not supported.")


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


def _create_team_and_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, int, str]:
    monkeypatch.chdir(tmp_path)
    init_db()
    skill_permissions_enforcer._global_enforcer = None
    enforcer = skill_permissions_enforcer.get_enforcer()
    enforcer.clear_policy()
    session = next(get_db())
    try:
        team = Team(name=f"team_{uuid4().hex}")
        session.add(team)
        session.commit()
        system = System(
            team_id=team.id,
            name=f"system_{uuid4().hex}",
            type=SystemType.OPERATION,
            agent_id_str=f"System1/{uuid4().hex}",
        )
        session.add(system)
        session.commit()
        return system.team_id, system.id, system.agent_id_str
    finally:
        session.close()


@pytest.fixture()
def allow_memory_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    def _allow(system_id: int, skill_name: str) -> tuple[bool, str | None]:
        return True, None

    monkeypatch.setattr(systems_service, "can_execute_skill", _allow)


def _entry(
    entry_id: str, content: str, *, layer: MemoryLayer = MemoryLayer.WORKING
) -> MemoryEntry:
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
        layer=layer,
        version=1,
        etag="etag-1",
    )


@pytest.mark.asyncio
async def test_list_returns_cursor_and_has_more(allow_memory_crud) -> None:
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
async def test_list_invalid_cursor_returns_invalid_params(allow_memory_crud) -> None:
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
async def test_list_filters_by_layer(allow_memory_crud) -> None:
    store = InMemoryCursorStore()
    store.add(_entry("mem-1", "first", layer=MemoryLayer.SESSION))
    store.add(_entry("mem-2", "second", layer=MemoryLayer.LONG_TERM))
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(action="list", namespace="root", layer="long_term"),
        CancellationToken(),
    )
    assert response.errors == []
    assert [item["id"] for item in response.items] == ["mem-2"]


@pytest.mark.asyncio
async def test_update_if_match_mismatch_creates_conflict(
    allow_memory_crud,
) -> None:
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
async def test_bulk_limit_exceeded_returns_invalid_params(allow_memory_crud) -> None:
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


@pytest.mark.asyncio
async def test_read_bulk_limit_exceeded_returns_invalid_params(
    allow_memory_crud,
) -> None:
    store = InMemoryCursorStore()
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(
            action="read",
            namespace="root",
            items=[{"entry_id": f"mem-{idx}"} for idx in range(11)],
        ),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_promote_bulk_limit_exceeded_returns_invalid_params(
    allow_memory_crud,
) -> None:
    store = InMemoryCursorStore()
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(
            action="promote",
            namespace="root",
            items=[
                {
                    "entry_id": f"mem-{idx}",
                    "target_scope": "team",
                }
                for idx in range(11)
            ],
        ),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_update_not_implemented_returns_error(allow_memory_crud) -> None:
    store = NotImplementedStore()
    store.add(_entry("mem-1", "original"))
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(
            action="update",
            namespace="root",
            items=[{"entry_id": "mem-1", "content": "new"}],
        ),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "NOT_IMPLEMENTED"


@pytest.mark.asyncio
async def test_delete_not_implemented_returns_error(allow_memory_crud) -> None:
    store = NotImplementedStore()
    store.add(_entry("mem-1", "original"))
    tool = _tool(store)
    response = await tool.run(
        MemoryCrudArgs(
            action="delete",
            namespace="root",
            items=[{"entry_id": "mem-1"}],
        ),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "NOT_IMPLEMENTED"


@pytest.mark.asyncio
async def test_permission_denied_returns_forbidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    team_id, system_id, agent_id_str = _create_team_and_system(tmp_path, monkeypatch)
    actor = MemoryActorContext(
        agent_id=agent_id_str,
        system_id=system_id,
        team_id=team_id,
        system_type=SystemType.OPERATION,
    )
    store = InMemoryCursorStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    tool = MemoryCrudTool(
        agent_id=AgentId.from_str(agent_id_str),
        service=service,
        actor_context=actor,
    )
    response = await tool.run(
        MemoryCrudArgs(action="list", namespace=agent_id_str),
        CancellationToken(),
    )
    assert response.errors
    assert response.errors[0].code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_permission_allowed_returns_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    team_id, system_id, agent_id_str = _create_team_and_system(tmp_path, monkeypatch)
    teams_service.add_allowed_skill(
        team_id=team_id,
        skill_name="memory_crud",
        actor_id="system5/root",
    )
    systems_service.add_skill_grant(
        system_id=system_id,
        skill_name="memory_crud",
        actor_id="system5/root",
    )
    actor = MemoryActorContext(
        agent_id=agent_id_str,
        system_id=system_id,
        team_id=team_id,
        system_type=SystemType.OPERATION,
    )
    store = InMemoryCursorStore()
    service = MemoryCrudService(registry=StaticScopeRegistry(store, store, store))
    tool = MemoryCrudTool(
        agent_id=AgentId.from_str(agent_id_str),
        service=service,
        actor_context=actor,
    )
    response = await tool.run(
        MemoryCrudArgs(action="list", namespace=agent_id_str),
        CancellationToken(),
    )
    assert response.errors == []
