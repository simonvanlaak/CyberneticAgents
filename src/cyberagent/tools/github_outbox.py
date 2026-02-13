from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


OUTBOX_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OutboxOp:
    """A queued GitHub operation.

    Attributes:
        id: DB primary key.
        kind: Operation type.
        payload: JSON payload (kind-specific).
        dedupe_key: Optional key used to avoid duplicates.
        attempts: Number of attempts so far.
        state: pending|sent|failed
        next_attempt_at: Unix epoch seconds at which this op is eligible to retry.
    """

    id: int
    kind: str
    payload: dict[str, Any]
    dedupe_key: Optional[str]
    attempts: int
    state: str
    next_attempt_at: float


class GitHubOutbox:
    """SQLite-backed outbox for rate-limit-aware GitHub automation."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox_ops (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at REAL NOT NULL,
                  kind TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  dedupe_key TEXT,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  last_error TEXT,
                  next_attempt_at REAL NOT NULL,
                  state TEXT NOT NULL DEFAULT 'pending'
                );
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_outbox_pending_dedupe
                ON outbox_ops(dedupe_key)
                WHERE dedupe_key IS NOT NULL AND state='pending';
                """
            )
            conn.execute(
                """
                INSERT INTO meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value;
                """,
                (str(OUTBOX_SCHEMA_VERSION),),
            )

    def enqueue(
        self,
        *,
        kind: str,
        payload: dict[str, Any],
        dedupe_key: Optional[str] = None,
        next_attempt_at: Optional[float] = None,
    ) -> bool:
        """Enqueue an operation.

        Returns:
            True if inserted, False if ignored due to dedupe.
        """

        now = time.time()
        eligible_at = float(next_attempt_at if next_attempt_at is not None else now)
        payload_json = json.dumps(payload, sort_keys=True)

        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO outbox_ops(created_at, kind, payload_json, dedupe_key, next_attempt_at, state)
                    VALUES(?, ?, ?, ?, ?, 'pending');
                    """,
                    (now, kind, payload_json, dedupe_key, eligible_at),
                )
                return True
            except sqlite3.IntegrityError:
                # Dedupe key collision (pending)
                return False

    def list_pending(self, *, limit: int = 50) -> list[OutboxOp]:
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, kind, payload_json, dedupe_key, attempts, state, next_attempt_at
                FROM outbox_ops
                WHERE state='pending' AND next_attempt_at <= ?
                ORDER BY id ASC
                LIMIT ?;
                """,
                (now, limit),
            ).fetchall()

        return [
            OutboxOp(
                id=int(r["id"]),
                kind=str(r["kind"]),
                payload=json.loads(str(r["payload_json"])),
                dedupe_key=(str(r["dedupe_key"]) if r["dedupe_key"] is not None else None),
                attempts=int(r["attempts"]),
                state=str(r["state"]),
                next_attempt_at=float(r["next_attempt_at"]),
            )
            for r in rows
        ]

    def mark_sent(self, op_ids: Sequence[int]) -> None:
        if not op_ids:
            return
        with self._connect() as conn:
            conn.executemany(
                "UPDATE outbox_ops SET state='sent' WHERE id=?;",
                [(int(i),) for i in op_ids],
            )

    def mark_failed(self, *, op_id: int, error: str, backoff_seconds: float) -> None:
        now = time.time()
        next_at = now + backoff_seconds
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE outbox_ops
                SET attempts = attempts + 1,
                    last_error = ?,
                    next_attempt_at = ?,
                    state='pending'
                WHERE id=?;
                """,
                (error[:8000], next_at, int(op_id)),
            )

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT state, COUNT(*) AS n
                FROM outbox_ops
                GROUP BY state;
                """
            ).fetchall()
        return {str(r["state"]): int(r["n"]) for r in rows}


def default_outbox_path() -> Path:
    # Keep it in repo-local data/ by default.
    return Path("data/github_outbox.db")
