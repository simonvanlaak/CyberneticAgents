from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

from src.cyberagent.memory.config import load_memory_backend_config


@dataclass(frozen=True)
class MemoryEntryView:
    id: str
    scope: str
    namespace: str
    owner_agent_id: str
    content_preview: str
    content_full: str
    tags: list[str]
    source: str
    priority: str
    layer: str
    confidence: float
    created_at: str
    updated_at: str


def load_memory_entries(
    *,
    scope: str | None = None,
    namespace: str | None = None,
    tag_contains: str | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[MemoryEntryView], int]:
    """
    Load memory entries from memory SQLite store for dashboard rendering.
    """
    config = load_memory_backend_config()
    conn = sqlite3.connect(config.sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                id, scope, namespace, owner_agent_id, content, tags, source,
                priority, layer, confidence, created_at, updated_at
            FROM memory_entries
            ORDER BY updated_at DESC
            """).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return [], 0
    finally:
        conn.close()

    entries = [_row_to_view(row) for row in rows]
    filtered = _filter_entries(
        entries,
        scope=scope,
        namespace=namespace,
        tag_contains=tag_contains,
        source=source,
    )
    total = len(filtered)
    if offset < 0:
        offset = 0
    if limit <= 0:
        return [], total
    return filtered[offset : offset + limit], total


def _row_to_view(row: sqlite3.Row) -> MemoryEntryView:
    content = str(row["content"])
    tags = _parse_tags(row["tags"])
    return MemoryEntryView(
        id=str(row["id"]),
        scope=str(row["scope"]),
        namespace=str(row["namespace"]),
        owner_agent_id=str(row["owner_agent_id"]),
        content_preview=_truncate_content(content),
        content_full=content,
        tags=tags,
        source=str(row["source"]),
        priority=str(row["priority"]),
        layer=str(row["layer"]),
        confidence=float(row["confidence"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _parse_tags(raw_tags: object) -> list[str]:
    if isinstance(raw_tags, str):
        try:
            parsed = json.loads(raw_tags)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _truncate_content(content: str, max_chars: int = 160) -> str:
    if len(content) <= max_chars:
        return content
    return f"{content[: max_chars - 3]}..."


def _filter_entries(
    entries: list[MemoryEntryView],
    *,
    scope: Optional[str],
    namespace: Optional[str],
    tag_contains: Optional[str],
    source: Optional[str],
) -> list[MemoryEntryView]:
    filtered = entries
    if scope:
        filtered = [entry for entry in filtered if entry.scope == scope]
    if namespace:
        filtered = [entry for entry in filtered if entry.namespace == namespace]
    if source:
        filtered = [entry for entry in filtered if entry.source == source]
    if tag_contains:
        needle = tag_contains.lower()
        filtered = [
            entry
            for entry in filtered
            if any(needle in tag.lower() for tag in entry.tags)
        ]
    return filtered
