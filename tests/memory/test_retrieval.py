from datetime import datetime, timezone

import pytest

from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.models import (
    MemoryAuditEvent,
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.observability import MemoryAuditSink, MemoryMetrics
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.cyberagent.memory.retrieval import (
    MemoryInjectionConfig,
    MemoryInjector,
    MemoryRetrievalService,
)
from src.cyberagent.memory.crud import MemoryActorContext
from src.enums import SystemType


def _entry(entry_id: str, content: str) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=content,
        tags=["onboarding"],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.8,
        layer=MemoryLayer.SESSION,
    )


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def test_retrieval_denies_global_for_sys1(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    registry = StaticScopeRegistry(store, store, store)
    service = MemoryRetrievalService(registry=registry)
    with pytest.raises(PermissionError):
        service.search_entries(
            actor=_actor(),
            scope=MemoryScope.GLOBAL,
            namespace="user",
            query_text="alpha",
            limit=5,
        )


def test_retrieval_and_injection_respects_budget(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    store.add(_entry("mem-1", "alpha " * 30))
    store.add(_entry("mem-2", "beta " * 30))

    registry = StaticScopeRegistry(store, store, store)
    metrics = MemoryMetrics()
    service = MemoryRetrievalService(registry=registry, metrics=metrics)
    result = service.search_entries(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root",
        query_text="alpha",
        limit=10,
    )
    injector = MemoryInjector(
        config=MemoryInjectionConfig(max_chars=80), metrics=metrics
    )
    injected = injector.build_prompt_entries(result.items)
    assert injected
    assert sum(len(entry) for entry in injected) <= 80
    assert metrics.injection_size_total <= 80


class _ListAuditSink(MemoryAuditSink):
    def __init__(self) -> None:
        self.events: list[MemoryAuditEvent] = []

    def record(self, event: MemoryAuditEvent) -> None:
        self.events.append(event)


def test_retrieval_logs_audit_events(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    store.add(_entry("mem-1", "alpha"))
    store.add(_entry("mem-2", "beta"))
    registry = StaticScopeRegistry(store, store, store)
    audit_sink = _ListAuditSink()
    service = MemoryRetrievalService(registry=registry, audit_sink=audit_sink)

    result = service.search_entries(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root",
        query_text="alpha",
        limit=10,
    )

    assert [entry.id for entry in result.items]
    ids = {event.resource_id for event in audit_sink.events}
    assert ids.issuperset({entry.id for entry in result.items})
    assert all(event.timestamp for event in audit_sink.events)
