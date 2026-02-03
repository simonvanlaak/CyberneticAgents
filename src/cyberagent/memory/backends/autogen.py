"""AutoGen memory adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from autogen_core.memory import Memory, MemoryContent, MemoryMimeType

from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryListResult,
    MemoryPriority,
    MemoryQuery,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.store import MemoryStore

_CURSOR_PREFIX = "offset:"


@dataclass(slots=True)
class AutoGenMemoryStore(MemoryStore):
    """Adapter that wraps AutoGen Memory implementations."""

    memory: Memory

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        content = _entry_to_memory_content(entry)
        _run_async(self.memory.add(content))
        return entry

    def get(
        self, entry_id: str, scope: MemoryScope, namespace: str
    ) -> MemoryEntry | None:
        entries = self._query_all(scope=scope, namespace=namespace)
        for entry in entries:
            if entry.id == entry_id:
                return entry
        return None

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        raise NotImplementedError("AutoGen memory does not support updates.")

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        raise NotImplementedError("AutoGen memory does not support deletes.")

    def query(self, query: MemoryQuery) -> MemoryListResult:
        text = query.text or ""
        result = _run_async(self.memory.query(text))
        entries = [
            _entry_from_memory_content(content)
            for content in result.results
            if _matches_query(content, query)
        ]
        return _slice_entries(entries, query.limit, query.cursor)

    def list(
        self,
        scope: MemoryScope,
        namespace: str,
        limit: int,
        cursor: str | None,
        owner_agent_id: str | None = None,
    ) -> MemoryListResult:
        entries = self._query_all(
            scope=scope, namespace=namespace, owner_agent_id=owner_agent_id
        )
        return _slice_entries(entries, limit, cursor)

    def _query_all(
        self,
        *,
        scope: MemoryScope,
        namespace: str,
        owner_agent_id: str | None = None,
    ) -> list[MemoryEntry]:
        result = _run_async(self.memory.query(""))
        entries = []
        for content in result.results:
            entry = _entry_from_memory_content(content)
            if entry.scope != scope or entry.namespace != namespace:
                continue
            if owner_agent_id and entry.owner_agent_id != owner_agent_id:
                continue
            entries.append(entry)
        return entries


def _matches_query(content: MemoryContent, query: MemoryQuery) -> bool:
    entry = _entry_from_memory_content(content)
    if entry.scope != query.scope or entry.namespace != query.namespace:
        return False
    if query.owner_agent_id and entry.owner_agent_id != query.owner_agent_id:
        return False
    if query.tags:
        if not set(query.tags).issubset(set(entry.tags)):
            return False
    return True


def _entry_to_memory_content(entry: MemoryEntry) -> MemoryContent:
    metadata = {
        "id": entry.id,
        "scope": entry.scope.value,
        "namespace": entry.namespace,
        "owner_agent_id": entry.owner_agent_id,
        "tags": list(entry.tags),
        "priority": entry.priority.value,
        "created_at": entry.created_at.isoformat(),
        "updated_at": (entry.updated_at or entry.created_at).isoformat(),
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "source": entry.source.value,
        "confidence": entry.confidence,
    }
    return MemoryContent(
        content=entry.content,
        mime_type=MemoryMimeType.TEXT,
        metadata=metadata,
    )


def _entry_from_memory_content(content: MemoryContent) -> MemoryEntry:
    if content.metadata is None:
        raise ValueError("MemoryContent metadata is required for adapter conversion.")
    metadata = content.metadata
    return MemoryEntry(
        id=str(metadata["id"]),
        scope=MemoryScope(str(metadata["scope"])),
        namespace=str(metadata["namespace"]),
        owner_agent_id=str(metadata["owner_agent_id"]),
        content=str(content.content),
        tags=list(metadata.get("tags", [])),
        priority=MemoryPriority(str(metadata["priority"])),
        created_at=_parse_datetime(metadata["created_at"]),
        updated_at=_parse_datetime(metadata["updated_at"]),
        expires_at=(
            _parse_datetime(metadata["expires_at"])
            if metadata.get("expires_at")
            else None
        ),
        source=MemorySource(str(metadata["source"])),
        confidence=float(metadata["confidence"]),
    )


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _slice_entries(
    entries: list[MemoryEntry], limit: int, cursor: str | None
) -> MemoryListResult:
    offset = _decode_cursor(cursor)
    end = offset + limit
    slice_entries = entries[offset:end]
    has_more = end < len(entries)
    next_cursor = _encode_cursor(end) if has_more else None
    return MemoryListResult(
        items=slice_entries, next_cursor=next_cursor, has_more=has_more
    )


def _encode_cursor(offset: int) -> str:
    return f"{_CURSOR_PREFIX}{offset}"


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    if not cursor.startswith(_CURSOR_PREFIX):
        raise ValueError("Invalid cursor format.")
    return int(cursor[len(_CURSOR_PREFIX) :])


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("AutoGenMemoryStore cannot run inside an active event loop.")
