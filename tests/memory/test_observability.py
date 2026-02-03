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
from src.cyberagent.memory.observability import MemoryAuditSink, MemoryMetrics
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
