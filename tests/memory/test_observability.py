from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryCreateRequest,
    MemoryCrudService,
    MemoryReadRequest,
)
from src.cyberagent.memory.models import (
    MemoryAuditEvent,
    MemoryEntry,
    MemoryListResult,
    MemoryPriority,
    MemoryQuery,
    MemoryScope,
    MemorySource,
)
import json
import logging

from src.cyberagent.memory.observability import (
    MemoryAuditSink,
    MemoryMetrics,
    MemoryMetricsReporter,
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
        items = list(self.entries.values())[:limit]
        return MemoryListResult(items=items, next_cursor=None, has_more=False)


class ListAuditSink(MemoryAuditSink):
    def __init__(self) -> None:
        self.events = []

    def record(self, event: MemoryAuditEvent) -> None:
        self.events.append(event)


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def test_metrics_and_audit_events() -> None:
    store = InMemoryStore()
    metrics = MemoryMetrics()
    audit_sink = ListAuditSink()
    service = MemoryCrudService(
        registry=StaticScopeRegistry(store, store, store),
        metrics=metrics,
        audit_sink=audit_sink,
    )
    service.create_entries(
        actor=_actor(),
        requests=[
            MemoryCreateRequest(
                content="hello",
                namespace="root",
                scope=MemoryScope.AGENT,
                tags=None,
                priority=MemoryPriority.MEDIUM,
                source=MemorySource.MANUAL,
                confidence=0.9,
                expires_at=None,
            )
        ],
    )
    service.read_entry(
        actor=_actor(),
        request=MemoryReadRequest(
            entry_id=list(store.entries.keys())[0],
            namespace="root",
            scope=MemoryScope.AGENT,
        ),
    )
    assert metrics.write_count == 1
    assert metrics.read_count == 1
    assert metrics.hit_rate == 1.0
    assert metrics.read_latency_ms_total >= 0.0
    assert len(audit_sink.events) >= 2


def test_metrics_reporter_logs_summary(caplog) -> None:
    reporter = MemoryMetricsReporter(interval_seconds=0.0)
    metrics = MemoryMetrics(reporter=reporter)
    with caplog.at_level(logging.INFO, logger="src.cyberagent.memory.observability"):
        metrics.record_read(hit=True)
        metrics.record_read_latency(12.5)
        metrics.record_query()
        metrics.record_query_latency(24.0)
        metrics.record_injection_size(120)
    record = [rec for rec in caplog.records if "memory_metrics" in rec.getMessage()][-1]
    payload = json.loads(record.getMessage().split(" ", 1)[1])
    assert payload["hit_rate"] == 1.0
    assert payload["injection_size_total"] == 120
    assert payload["query_latency_ms_total"] == 24.0
