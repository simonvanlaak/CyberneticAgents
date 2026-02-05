"""SQLite-backed memory record store."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryListResult,
    MemoryPriority,
    MemoryQuery,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.store import MemoryStore

_CURSOR_PREFIX = "offset:"


@dataclass(slots=True)
class SqliteMemoryStore(MemoryStore):
    """SQLite implementation for memory CRUD and keyword search."""

    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self._execute(
            """
            INSERT INTO memory_entries (
                id, scope, namespace, owner_agent_id, content, tags, priority,
                created_at, updated_at, expires_at, source, confidence, layer,
                version, etag, conflict, conflict_of
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.scope.value,
                entry.namespace,
                entry.owner_agent_id,
                entry.content,
                json.dumps(entry.tags),
                entry.priority.value,
                entry.created_at.isoformat(),
                (entry.updated_at or entry.created_at).isoformat(),
                entry.expires_at.isoformat() if entry.expires_at else None,
                entry.source.value,
                entry.confidence,
                entry.layer.value,
                entry.version,
                entry.etag,
                int(entry.conflict),
                entry.conflict_of,
            ),
        )
        return entry

    def get(
        self, entry_id: str, scope: MemoryScope, namespace: str
    ) -> MemoryEntry | None:
        rows = self._fetch(
            "SELECT * FROM memory_entries WHERE id = ? AND scope = ? AND namespace = ?",
            (entry_id, scope.value, namespace),
        )
        if not rows:
            return None
        return _row_to_entry(rows[0])

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        self._execute(
            """
            UPDATE memory_entries
            SET content = ?, tags = ?, priority = ?, updated_at = ?, expires_at = ?,
                source = ?, confidence = ?, layer = ?, version = ?, etag = ?,
                conflict = ?, conflict_of = ?, owner_agent_id = ?
            WHERE id = ? AND scope = ? AND namespace = ?
            """,
            (
                entry.content,
                json.dumps(entry.tags),
                entry.priority.value,
                (entry.updated_at or entry.created_at).isoformat(),
                entry.expires_at.isoformat() if entry.expires_at else None,
                entry.source.value,
                entry.confidence,
                entry.layer.value,
                entry.version,
                entry.etag,
                int(entry.conflict),
                entry.conflict_of,
                entry.owner_agent_id,
                entry.id,
                entry.scope.value,
                entry.namespace,
            ),
        )
        return entry

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        cursor = self._execute(
            "DELETE FROM memory_entries WHERE id = ? AND scope = ? AND namespace = ?",
            (entry_id, scope.value, namespace),
        )
        return cursor.rowcount > 0

    def query(self, query: MemoryQuery) -> MemoryListResult:
        entries = self._fetch_scope_entries(query.scope, query.namespace)
        filtered = _filter_entries(entries, query)
        ranked = _rank_entries(filtered, query.text)
        return _slice_entries(ranked, query.limit, query.cursor)

    def list(
        self,
        scope: MemoryScope,
        namespace: str,
        limit: int,
        cursor: str | None,
        owner_agent_id: str | None = None,
    ) -> MemoryListResult:
        entries = self._fetch_scope_entries(scope, namespace)
        if owner_agent_id:
            entries = [
                entry for entry in entries if entry.owner_agent_id == owner_agent_id
            ]
        return _slice_entries(entries, limit, cursor)

    def _fetch_scope_entries(
        self, scope: MemoryScope, namespace: str
    ) -> list[MemoryEntry]:
        rows = self._fetch(
            """
            SELECT * FROM memory_entries
            WHERE scope = ? AND namespace = ?
            ORDER BY created_at ASC
            """,
            (scope.value, namespace),
        )
        return [_row_to_entry(row) for row in rows]

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    owner_agent_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    layer TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    etag TEXT NOT NULL,
                    conflict INTEGER NOT NULL,
                    conflict_of TEXT
                )
                """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_entries(scope)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_namespace ON memory_entries(namespace)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _execute(self, query: str, params: Iterable[object]) -> sqlite3.Cursor:
        with self._connect() as connection:
            cursor = connection.execute(query, tuple(params))
            connection.commit()
            return cursor

    def _fetch(self, query: str, params: Iterable[object]) -> list[sqlite3.Row]:
        with self._connect() as connection:
            cursor = connection.execute(query, tuple(params))
            return list(cursor.fetchall())


def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
    return MemoryEntry(
        id=str(row["id"]),
        scope=MemoryScope(str(row["scope"])),
        namespace=str(row["namespace"]),
        owner_agent_id=str(row["owner_agent_id"]),
        content=str(row["content"]),
        tags=list(json.loads(row["tags"])),
        priority=MemoryPriority(str(row["priority"])),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        expires_at=_parse_datetime(row["expires_at"]) if row["expires_at"] else None,
        source=MemorySource(str(row["source"])),
        confidence=float(row["confidence"]),
        layer=MemoryLayer(str(row["layer"])),
        version=int(row["version"]),
        etag=str(row["etag"]),
        conflict=bool(row["conflict"]),
        conflict_of=row["conflict_of"],
    )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _filter_entries(
    entries: list[MemoryEntry], query: MemoryQuery
) -> list[MemoryEntry]:
    filtered = entries
    if query.layer is not None:
        filtered = [entry for entry in filtered if entry.layer == query.layer]
    if query.owner_agent_id is not None:
        filtered = [
            entry for entry in filtered if entry.owner_agent_id == query.owner_agent_id
        ]
    if query.tags:
        required = set(query.tags)
        filtered = [entry for entry in filtered if required.issubset(set(entry.tags))]
    if query.text:
        filtered = [entry for entry in filtered if _score_entry(entry, query.text) > 0]
    return filtered


def _rank_entries(
    entries: list[MemoryEntry], query_text: str | None
) -> list[MemoryEntry]:
    if not query_text:
        return entries
    return sorted(
        entries,
        key=lambda entry: (_score_entry(entry, query_text), entry.updated_at),
        reverse=True,
    )


def _score_entry(entry: MemoryEntry, query_text: str) -> int:
    query = query_text.lower()
    haystack = f"{entry.content} {' '.join(entry.tags)}".lower()
    if not query:
        return 0
    tokens = set(query.split())
    haystack_tokens = set(haystack.split())
    keyword_score = sum(1 for token in tokens if token in haystack_tokens)
    fuzzy_score = int(SequenceMatcher(None, query, entry.content.lower()).ratio() * 2)
    return keyword_score + fuzzy_score


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
