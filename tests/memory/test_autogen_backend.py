import datetime

import pytest
from autogen_core.memory import ListMemory

from src.cyberagent.memory.backends.autogen import AutoGenMemoryStore
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)


def _entry(entry_id: str) -> MemoryEntry:
    now = datetime.datetime.now(datetime.timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=f"content-{entry_id}",
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        source=MemorySource.MANUAL,
        confidence=0.9,
    )


def test_autogen_store_add_and_get() -> None:
    memory = ListMemory(name="test")
    store = AutoGenMemoryStore(memory)
    store.add(_entry("mem-1"))
    result = store.get("mem-1", MemoryScope.AGENT, "root")
    assert result is not None
    assert result.content == "content-mem-1"


def test_autogen_store_list_uses_cursor() -> None:
    memory = ListMemory(name="test")
    store = AutoGenMemoryStore(memory)
    for idx in range(3):
        store.add(_entry(f"mem-{idx}"))
    first_page = store.list(MemoryScope.AGENT, "root", limit=2, cursor=None)
    assert first_page.has_more is True
    assert first_page.next_cursor is not None
    second_page = store.list(
        MemoryScope.AGENT, "root", limit=2, cursor=first_page.next_cursor
    )
    assert second_page.has_more is False
    assert len(second_page.items) == 1


def test_autogen_store_update_raises() -> None:
    memory = ListMemory(name="test")
    store = AutoGenMemoryStore(memory)
    with pytest.raises(NotImplementedError):
        store.update(_entry("mem-2"))
