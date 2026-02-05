from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.models import MemoryLayer, MemoryScope
from src.cyberagent.memory.reflection import (
    MemoryReflectionConfig,
    MemoryReflectionService,
)
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.enums import SystemType


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys4",
        system_id=4,
        team_id=1,
        system_type=SystemType.INTELLIGENCE,
    )


def test_reflection_writes_summary(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    registry = StaticScopeRegistry(store, store, store)
    service = MemoryReflectionService(
        registry=registry,
        config=MemoryReflectionConfig(max_chars=60),
    )
    entry = service.reflect_and_store(
        actor=_actor(),
        scope=MemoryScope.GLOBAL,
        namespace="user",
        session_logs=["first insight", "second insight", "third insight"],
        layer=MemoryLayer.META,
    )
    assert entry is not None
    assert entry.scope == MemoryScope.GLOBAL
    assert entry.layer == MemoryLayer.META
    assert len(entry.content) <= 60
