"""Hybrid memory store combining record storage and vector search."""

from __future__ import annotations

from dataclasses import dataclass

from src.cyberagent.memory.backends.vector_index import MemoryVectorIndex
from src.cyberagent.memory.models import MemoryEntry, MemoryListResult, MemoryQuery
from src.cyberagent.memory.store import MemoryStore

_CURSOR_PREFIX = "offset:"


@dataclass(slots=True)
class HybridMemoryStore(MemoryStore):
    """Record store with optional vector index for semantic queries."""

    record_store: MemoryStore
    vector_index: MemoryVectorIndex

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        created = self.record_store.add(entry)
        self.vector_index.upsert(entry)
        return created

    def get(self, entry_id: str, scope, namespace):  # type: ignore[override]
        return self.record_store.get(entry_id, scope, namespace)

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        updated = self.record_store.update(entry)
        self.vector_index.upsert(entry)
        return updated

    def delete(self, entry_id: str, scope, namespace):  # type: ignore[override]
        deleted = self.record_store.delete(entry_id, scope, namespace)
        if deleted:
            self.vector_index.delete(entry_id)
        return deleted

    def query(self, query: MemoryQuery) -> MemoryListResult:
        keyword_result = self.record_store.query(query)
        if not query.text:
            return keyword_result
        vector_ids = self.vector_index.query(query.text, query.limit)
        merged = list(keyword_result.items)
        seen = {entry.id for entry in merged}
        for entry_id in vector_ids:
            if entry_id in seen:
                continue
            entry = self.record_store.get(entry_id, query.scope, query.namespace)
            if entry is None:
                continue
            if query.layer and entry.layer != query.layer:
                continue
            if query.owner_agent_id and entry.owner_agent_id != query.owner_agent_id:
                continue
            if query.tags and not set(query.tags).issubset(set(entry.tags)):
                continue
            merged.append(entry)
            seen.add(entry_id)
        return _slice_entries(merged, query.limit, query.cursor)

    def list(self, scope, namespace, limit, cursor, owner_agent_id=None):  # type: ignore[override]
        return self.record_store.list(scope, namespace, limit, cursor, owner_agent_id)


def _slice_entries(
    entries: list[MemoryEntry], limit: int, cursor: str | None
) -> MemoryListResult:
    offset = _decode_cursor(cursor)
    end = offset + limit
    items = entries[offset:end]
    has_more = end < len(entries)
    next_cursor = _encode_cursor(end) if has_more else None
    return MemoryListResult(items=items, next_cursor=next_cursor, has_more=has_more)


def _encode_cursor(offset: int) -> str:
    return f"{_CURSOR_PREFIX}{offset}"


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    if not cursor.startswith(_CURSOR_PREFIX):
        raise ValueError("Invalid cursor format.")
    return int(cursor[len(_CURSOR_PREFIX) :])
