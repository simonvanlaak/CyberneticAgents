from __future__ import annotations

import sqlite3
from pathlib import Path

from src.cyberagent.ui import memory_data


def _create_memory_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("""
            CREATE TABLE memory_entries (
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
        conn.executemany(
            """
            INSERT INTO memory_entries (
                id, scope, namespace, owner_agent_id, content, tags, priority,
                created_at, updated_at, expires_at, source, confidence, layer,
                version, etag, conflict, conflict_of
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "mem-1",
                    "global",
                    "user",
                    "System4/root",
                    "PKM file: notes/alpha.md\n\nAlpha text",
                    '["onboarding","pkm","pkm_file"]',
                    "high",
                    "2026-02-09T12:00:00+00:00",
                    "2026-02-09T12:00:00+00:00",
                    None,
                    "import",
                    0.8,
                    "long_term",
                    1,
                    "etag-1",
                    0,
                    None,
                ),
                (
                    "mem-2",
                    "global",
                    "user",
                    "System4/root",
                    "Profile link summary",
                    '["onboarding","profile_link"]',
                    "medium",
                    "2026-02-09T12:01:00+00:00",
                    "2026-02-09T12:01:00+00:00",
                    None,
                    "tool",
                    0.6,
                    "session",
                    1,
                    "etag-2",
                    0,
                    None,
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_load_memory_entries_filters_and_preview(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    _create_memory_db(db_path)
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(db_path))

    entries, total = memory_data.load_memory_entries(
        scope="global",
        namespace="user",
        tag_contains="pkm_file",
        source="import",
        limit=50,
    )

    assert total == 1
    assert len(entries) == 1
    assert entries[0].id == "mem-1"
    assert "pkm_file" in entries[0].tags
    assert "PKM file: notes/alpha.md" in entries[0].content_preview
