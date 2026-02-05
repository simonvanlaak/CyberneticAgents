from datetime import datetime, timezone

from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.memengine import MemEngine, MemEngineConfig
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.enums import SystemType


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def _entry(entry_id: str, content: str) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=content,
        tags=["alpha"],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.9,
        layer=MemoryLayer.SESSION,
    )


def test_memengine_search_and_summarize(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    store.add(_entry("mem-1", "alpha beta"))
    registry = StaticScopeRegistry(store, store, store)
    engine = MemEngine(registry=registry, config=MemEngineConfig(max_summary_chars=20))
    result = engine.search_entries(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root",
        query_text="alpha",
        limit=5,
    )
    assert result.items
    summary = engine.summarize(["one", "two", "three"])
    assert len(summary) <= 20
