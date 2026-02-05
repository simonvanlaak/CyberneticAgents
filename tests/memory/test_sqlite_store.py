from datetime import datetime, timezone

from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryListResult,
    MemoryPriority,
    MemoryQuery,
    MemoryScope,
    MemorySource,
)


def _entry(
    entry_id: str,
    content: str,
    *,
    namespace: str = "root",
    tags: list[str] | None = None,
) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace=namespace,
        owner_agent_id="root_sys1",
        content=content,
        tags=tags or ["alpha"],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.9,
        layer=MemoryLayer.SESSION,
    )


def test_sqlite_store_crud_roundtrip(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    entry = _entry("mem-1", "hello world")
    store.add(entry)

    fetched = store.get("mem-1", MemoryScope.AGENT, "root")
    assert fetched is not None
    assert fetched.content == "hello world"

    entry.content = "updated"
    entry.version += 1
    entry.etag = "etag-2"
    store.update(entry)

    updated = store.get("mem-1", MemoryScope.AGENT, "root")
    assert updated is not None
    assert updated.content == "updated"
    assert updated.version == 2

    assert store.delete("mem-1", MemoryScope.AGENT, "root") is True
    assert store.get("mem-1", MemoryScope.AGENT, "root") is None


def test_sqlite_store_list_pagination(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    store.add(_entry("mem-1", "one"))
    store.add(_entry("mem-2", "two"))
    store.add(_entry("mem-3", "three"))

    page1 = store.list(MemoryScope.AGENT, "root", limit=2, cursor=None)
    assert isinstance(page1, MemoryListResult)
    assert len(page1.items) == 2
    assert page1.has_more is True
    assert page1.next_cursor is not None

    page2 = store.list(MemoryScope.AGENT, "root", limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 1
    assert page2.has_more is False
    assert page2.next_cursor is None


def test_sqlite_store_query_filters(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    store.add(_entry("mem-1", "alpha beta gamma", tags=["alpha"]))
    store.add(_entry("mem-2", "delta epsilon", tags=["delta"]))
    store.add(_entry("mem-3", "alpha delta", namespace="other", tags=["alpha"]))

    query = MemoryQuery(
        text="alpha",
        scope=MemoryScope.AGENT,
        namespace="root",
        limit=10,
    )
    result = store.query(query)
    assert len(result.items) == 1
    assert result.items[0].id == "mem-1"
