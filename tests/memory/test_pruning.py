from datetime import datetime, timedelta, timezone

from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.pruning import MemoryPruner, MemoryPruningConfig
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.enums import SystemType


def _entry(entry_id: str, *, priority: MemoryPriority, expires_at=None) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=f"content {entry_id}",
        tags=[],
        priority=priority,
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
        source=MemorySource.MANUAL,
        confidence=0.7,
        layer=MemoryLayer.SESSION,
    )


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def test_prune_removes_expired_entries(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    store.add(_entry("mem-1", priority=MemoryPriority.LOW, expires_at=expired))
    store.add(_entry("mem-2", priority=MemoryPriority.MEDIUM))

    pruner = MemoryPruner(
        registry=StaticScopeRegistry(store, store, store),
        config=MemoryPruningConfig(max_entries_per_namespace=10),
    )
    deleted = pruner.prune(actor=_actor(), scope=MemoryScope.AGENT, namespace="root")
    assert "mem-1" in deleted
    assert store.get("mem-1", MemoryScope.AGENT, "root") is None


def test_prune_respects_priority(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    store.add(_entry("low", priority=MemoryPriority.LOW))
    store.add(_entry("med", priority=MemoryPriority.MEDIUM))
    store.add(_entry("high", priority=MemoryPriority.HIGH))

    pruner = MemoryPruner(
        registry=StaticScopeRegistry(store, store, store),
        config=MemoryPruningConfig(max_entries_per_namespace=2),
    )
    deleted = pruner.prune(actor=_actor(), scope=MemoryScope.AGENT, namespace="root")
    assert "low" in deleted
    assert store.get("low", MemoryScope.AGENT, "root") is None
    assert store.get("high", MemoryScope.AGENT, "root") is not None
