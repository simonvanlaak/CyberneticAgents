from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.cyberagent.core.paths import resolve_data_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueuedSuggestion:
    path: Path
    payload_text: str
    idempotency_key: str
    queued_at: float


@dataclass(frozen=True)
class QueuedAgentMessage:
    path: Path
    recipient: str
    sender: str | None
    message_type: str
    payload: dict[str, Any]
    idempotency_key: str
    queued_at: float
    attempts: int
    next_attempt_at: float


class RuntimeQueueBackend(Protocol):
    """Contract for runtime suggestion + agent-message queue backends."""

    def enqueue_suggestion(
        self, payload_text: str, idempotency_key: str | None = None
    ) -> Path: ...

    def read_queued_suggestions(self) -> list[QueuedSuggestion]: ...

    def ack_suggestion(self, path: Path) -> None: ...

    def enqueue_agent_message(
        self,
        *,
        recipient: str,
        sender: str | None,
        message_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Path: ...

    def read_queued_agent_messages(self) -> list[QueuedAgentMessage]: ...

    def ack_agent_message(self, path: Path) -> None: ...

    def list_dead_letter_agent_messages(self) -> list[QueuedAgentMessage]: ...

    def requeue_dead_letter_agent_message(self, path: Path) -> Path | None: ...

    def defer_agent_message(
        self,
        *,
        path: Path,
        error: str,
        now_ts: float | None = None,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 300.0,
        max_attempts: int = 8,
    ) -> bool: ...


class FileRuntimeQueueBackend:
    """Filesystem-backed queue backend (default)."""

    def __init__(
        self,
        *,
        suggest_queue_dir: Path,
        agent_message_queue_dir: Path,
        agent_message_dead_letter_dir: Path,
    ) -> None:
        self._suggest_queue_dir = suggest_queue_dir
        self._agent_message_queue_dir = agent_message_queue_dir
        self._agent_message_dead_letter_dir = agent_message_dead_letter_dir

    def enqueue_suggestion(
        self, payload_text: str, idempotency_key: str | None = None
    ) -> Path:
        self._suggest_queue_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "payload_text": payload_text,
            "idempotency_key": idempotency_key
            or _build_suggestion_idempotency_key(payload_text),
            "queued_at": time.time(),
        }
        file_id = f"{time.time_ns()}_{uuid.uuid4().hex}"
        target = self._suggest_queue_dir / f"{file_id}.json"
        _write_json_atomically(target, payload)
        return target

    def read_queued_suggestions(self) -> list[QueuedSuggestion]:
        if not self._suggest_queue_dir.exists():
            return []
        suggestions: list[QueuedSuggestion] = []
        for path in sorted(self._suggest_queue_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to read suggestion %s: %s", path, exc)
                continue
            payload_text = data.get("payload_text")
            if not isinstance(payload_text, str):
                logger.warning("Suggestion %s missing payload_text", path)
                continue
            raw_idempotency_key = data.get("idempotency_key")
            idempotency_key = (
                raw_idempotency_key
                if isinstance(raw_idempotency_key, str) and raw_idempotency_key
                else _build_suggestion_idempotency_key(payload_text)
            )
            queued_at = data.get("queued_at")
            queued_at_value = queued_at if isinstance(queued_at, (int, float)) else 0.0
            suggestions.append(
                QueuedSuggestion(
                    path=path,
                    payload_text=payload_text,
                    idempotency_key=idempotency_key,
                    queued_at=queued_at_value,
                )
            )
        return suggestions

    def ack_suggestion(self, path: Path) -> None:
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Failed to remove suggestion %s: %s", path, exc)

    def enqueue_agent_message(
        self,
        *,
        recipient: str,
        sender: str | None,
        message_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Path:
        self._agent_message_queue_dir.mkdir(parents=True, exist_ok=True)
        resolved_idempotency_key = idempotency_key or _build_agent_message_idempotency_key(
            recipient=recipient,
            sender=sender,
            message_type=message_type,
            payload=payload,
        )
        existing_path = self._find_queued_message_by_idempotency_key(
            resolved_idempotency_key
        )
        if existing_path is not None:
            return existing_path

        payload_data = {
            "recipient": recipient,
            "sender": sender,
            "message_type": message_type,
            "payload": payload,
            "idempotency_key": resolved_idempotency_key,
            "queued_at": time.time(),
            "attempts": 0,
            "next_attempt_at": 0.0,
        }
        file_id = f"{time.time_ns()}_{uuid.uuid4().hex}"
        target = self._agent_message_queue_dir / f"{file_id}.json"
        _write_json_atomically(target, payload_data)
        return target

    def read_queued_agent_messages(self) -> list[QueuedAgentMessage]:
        return self._read_agent_messages_from_dir(self._agent_message_queue_dir)

    def ack_agent_message(self, path: Path) -> None:
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Failed to remove agent message %s: %s", path, exc)

    def list_dead_letter_agent_messages(self) -> list[QueuedAgentMessage]:
        return self._read_agent_messages_from_dir(self._agent_message_dead_letter_dir)

    def requeue_dead_letter_agent_message(self, path: Path) -> Path | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to read dead-letter message %s for requeue: %s", path, exc
            )
            return None
        data.pop("dead_lettered_at", None)
        data.pop("last_error", None)
        data.pop("last_failed_at", None)
        data["attempts"] = 0
        data["next_attempt_at"] = 0.0
        self._agent_message_queue_dir.mkdir(parents=True, exist_ok=True)
        target = self._agent_message_queue_dir / path.name
        try:
            _write_json_atomically(target, data)
            path.unlink(missing_ok=True)
            return target
        except OSError as exc:
            logger.warning("Failed to requeue dead-letter message %s: %s", path, exc)
            return None

    def defer_agent_message(
        self,
        *,
        path: Path,
        error: str,
        now_ts: float | None = None,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 300.0,
        max_attempts: int = 8,
    ) -> bool:
        timestamp = time.time() if now_ts is None else now_ts
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read agent message %s for defer: %s", path, exc)
            return False

        attempts_raw = data.get("attempts")
        attempts = (
            attempts_raw if isinstance(attempts_raw, int) and attempts_raw >= 0 else 0
        )
        attempts += 1
        data["attempts"] = attempts
        data["last_error"] = str(error)
        data["last_failed_at"] = timestamp

        if attempts >= max_attempts:
            self._agent_message_dead_letter_dir.mkdir(parents=True, exist_ok=True)
            target = self._agent_message_dead_letter_dir / path.name
            data["dead_lettered_at"] = timestamp
            try:
                _write_json_atomically(target, data)
                path.unlink(missing_ok=True)
                logger.error("Moved agent message to dead-letter: %s", target)
                return True
            except OSError as exc:
                logger.warning(
                    "Failed to move agent message %s to dead-letter: %s", path, exc
                )
                return False

        delay = min(base_delay_seconds * (2 ** max(0, attempts - 1)), max_delay_seconds)
        data["next_attempt_at"] = timestamp + delay
        try:
            _write_json_atomically(path, data)
        except OSError as exc:
            logger.warning("Failed to update deferred agent message %s: %s", path, exc)
        return False

    def _find_queued_message_by_idempotency_key(self, idempotency_key: str) -> Path | None:
        if not self._agent_message_queue_dir.exists():
            return None
        for path in sorted(self._agent_message_queue_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            queued_key = data.get("idempotency_key")
            if queued_key == idempotency_key:
                return path
        return None

    def _read_agent_messages_from_dir(self, directory: Path) -> list[QueuedAgentMessage]:
        if not directory.exists():
            return []
        messages: list[QueuedAgentMessage] = []
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to read agent message %s: %s", path, exc)
                continue
            parsed = _parse_agent_message(path=path, data=data)
            if parsed is not None:
                messages.append(parsed)
        return messages


class SQLiteRuntimeQueueBackend:
    """SQLite-backed queue backend for safer multi-process coordination."""

    _SUGGESTION_TOKEN_PREFIX = "sqlite_suggestion_"
    _AGENT_TOKEN_PREFIX = "sqlite_agent_"
    _AGENT_DEAD_TOKEN_PREFIX = "sqlite_dead_agent_"

    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def enqueue_suggestion(
        self, payload_text: str, idempotency_key: str | None = None
    ) -> Path:
        queued_at = time.time()
        resolved_key = idempotency_key or _build_suggestion_idempotency_key(payload_text)
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO queue_suggestions(payload_text, idempotency_key, queued_at)
                VALUES(?, ?, ?)
                RETURNING id;
                """,
                (payload_text, resolved_key, queued_at),
            ).fetchone()
            if row is None:
                raise RuntimeError("failed to enqueue suggestion")
            return self._suggestion_token(int(row[0]))

    def read_queued_suggestions(self) -> list[QueuedSuggestion]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, payload_text, idempotency_key, queued_at
                FROM queue_suggestions
                ORDER BY id ASC;
                """
            ).fetchall()
        return [
            QueuedSuggestion(
                path=self._suggestion_token(int(row["id"])),
                payload_text=str(row["payload_text"]),
                idempotency_key=str(row["idempotency_key"]),
                queued_at=float(row["queued_at"]),
            )
            for row in rows
        ]

    def ack_suggestion(self, path: Path) -> None:
        suggestion_id = self._decode_token(path, self._SUGGESTION_TOKEN_PREFIX)
        if suggestion_id is None:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM queue_suggestions WHERE id=?;", (suggestion_id,))

    def enqueue_agent_message(
        self,
        *,
        recipient: str,
        sender: str | None,
        message_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Path:
        resolved_idempotency_key = idempotency_key or _build_agent_message_idempotency_key(
            recipient=recipient,
            sender=sender,
            message_type=message_type,
            payload=payload,
        )
        payload_json = json.dumps(payload, sort_keys=True)
        queued_at = time.time()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM queue_agent_messages
                WHERE state='pending' AND idempotency_key=?
                LIMIT 1;
                """,
                (resolved_idempotency_key,),
            ).fetchone()
            if existing is not None:
                return self._agent_token(int(existing["id"]))

            row = conn.execute(
                """
                INSERT INTO queue_agent_messages(
                    recipient,
                    sender,
                    message_type,
                    payload_json,
                    idempotency_key,
                    queued_at,
                    attempts,
                    next_attempt_at,
                    state
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 0.0, 'pending')
                RETURNING id;
                """,
                (
                    recipient,
                    sender,
                    message_type,
                    payload_json,
                    resolved_idempotency_key,
                    queued_at,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("failed to enqueue agent message")
            return self._agent_token(int(row[0]))

    def read_queued_agent_messages(self) -> list[QueuedAgentMessage]:
        return self._read_agent_messages(state="pending")

    def ack_agent_message(self, path: Path) -> None:
        message_id = self._decode_token(path, self._AGENT_TOKEN_PREFIX)
        if message_id is None:
            return
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM queue_agent_messages WHERE id=? AND state='pending';",
                (message_id,),
            )

    def list_dead_letter_agent_messages(self) -> list[QueuedAgentMessage]:
        return self._read_agent_messages(state="dead_letter")

    def requeue_dead_letter_agent_message(self, path: Path) -> Path | None:
        message_id = self._decode_token(path, self._AGENT_DEAD_TOKEN_PREFIX)
        if message_id is None:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM queue_agent_messages
                WHERE id=? AND state='dead_letter'
                LIMIT 1;
                """,
                (message_id,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE queue_agent_messages
                SET state='pending',
                    attempts=0,
                    next_attempt_at=0.0,
                    dead_lettered_at=NULL,
                    last_error=NULL,
                    last_failed_at=NULL
                WHERE id=?;
                """,
                (message_id,),
            )
        return self._agent_token(message_id)

    def defer_agent_message(
        self,
        *,
        path: Path,
        error: str,
        now_ts: float | None = None,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 300.0,
        max_attempts: int = 8,
    ) -> bool:
        message_id = self._decode_token(path, self._AGENT_TOKEN_PREFIX)
        if message_id is None:
            return False

        timestamp = time.time() if now_ts is None else now_ts
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT attempts
                FROM queue_agent_messages
                WHERE id=? AND state='pending'
                LIMIT 1;
                """,
                (message_id,),
            ).fetchone()
            if row is None:
                return False
            attempts = int(row["attempts"]) + 1

            if attempts >= max_attempts:
                conn.execute(
                    """
                    UPDATE queue_agent_messages
                    SET attempts=?,
                        state='dead_letter',
                        next_attempt_at=0.0,
                        last_error=?,
                        last_failed_at=?,
                        dead_lettered_at=?
                    WHERE id=?;
                    """,
                    (attempts, str(error), timestamp, timestamp, message_id),
                )
                return True

            delay = min(base_delay_seconds * (2 ** max(0, attempts - 1)), max_delay_seconds)
            conn.execute(
                """
                UPDATE queue_agent_messages
                SET attempts=?,
                    next_attempt_at=?,
                    last_error=?,
                    last_failed_at=?
                WHERE id=?;
                """,
                (attempts, timestamp + delay, str(error), timestamp, message_id),
            )
        return False

    def _read_agent_messages(self, *, state: str) -> list[QueuedAgentMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, recipient, sender, message_type, payload_json, idempotency_key,
                       queued_at, attempts, next_attempt_at
                FROM queue_agent_messages
                WHERE state=?
                ORDER BY id ASC;
                """,
                (state,),
            ).fetchall()

        messages: list[QueuedAgentMessage] = []
        for row in rows:
            payload_json = row["payload_json"]
            try:
                payload = json.loads(str(payload_json))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Failed to decode SQLite queued agent message payload id=%s: %s",
                    row["id"],
                    exc,
                )
                continue
            if not isinstance(payload, dict):
                logger.warning(
                    "SQLite queued agent message payload id=%s is not an object",
                    row["id"],
                )
                continue
            token = (
                self._agent_token(int(row["id"]))
                if state == "pending"
                else self._agent_dead_token(int(row["id"]))
            )
            messages.append(
                QueuedAgentMessage(
                    path=token,
                    recipient=str(row["recipient"]),
                    sender=str(row["sender"]) if row["sender"] is not None else None,
                    message_type=str(row["message_type"]),
                    payload=payload,
                    idempotency_key=str(row["idempotency_key"]),
                    queued_at=float(row["queued_at"]),
                    attempts=int(row["attempts"]),
                    next_attempt_at=float(row["next_attempt_at"]),
                )
            )
        return messages

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_text TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    queued_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    sender TEXT,
                    message_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    queued_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL DEFAULT 0.0,
                    state TEXT NOT NULL CHECK (state IN ('pending', 'dead_letter')),
                    last_error TEXT,
                    last_failed_at REAL,
                    dead_lettered_at REAL
                );
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_agent_pending_idempotency
                    ON queue_agent_messages(idempotency_key)
                    WHERE state='pending';
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_agent_state_next_attempt
                    ON queue_agent_messages(state, next_attempt_at, queued_at);
                """
            )

    def _suggestion_token(self, suggestion_id: int) -> Path:
        return Path(f"{self._SUGGESTION_TOKEN_PREFIX}{suggestion_id}.json")

    def _agent_token(self, message_id: int) -> Path:
        return Path(f"{self._AGENT_TOKEN_PREFIX}{message_id}.json")

    def _agent_dead_token(self, message_id: int) -> Path:
        return Path(f"{self._AGENT_DEAD_TOKEN_PREFIX}{message_id}.json")

    @staticmethod
    def _decode_token(path: Path, prefix: str) -> int | None:
        token = path.name
        if not token.startswith(prefix) or not token.endswith(".json"):
            return None
        numeric = token[len(prefix) : -5]
        try:
            return int(numeric)
        except ValueError:
            return None


def build_runtime_queue_backend(
    *,
    backend: str,
    suggest_queue_dir: Path,
    agent_message_queue_dir: Path,
    agent_message_dead_letter_dir: Path,
    sqlite_db_path: Path,
) -> RuntimeQueueBackend:
    """Create the requested queue backend implementation."""

    normalized_backend = backend.strip().lower()
    if normalized_backend in {"", "file"}:
        return FileRuntimeQueueBackend(
            suggest_queue_dir=suggest_queue_dir,
            agent_message_queue_dir=agent_message_queue_dir,
            agent_message_dead_letter_dir=agent_message_dead_letter_dir,
        )
    if normalized_backend == "sqlite":
        return SQLiteRuntimeQueueBackend(db_path=sqlite_db_path)
    raise ValueError(f"Unsupported runtime queue backend: {backend}")


def default_sqlite_queue_path() -> Path:
    """Default SQLite queue database path."""

    return resolve_data_path("runtime_queue.db")


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _parse_agent_message(path: Path, data: dict[str, Any]) -> QueuedAgentMessage | None:
    recipient = data.get("recipient")
    message_type = data.get("message_type")
    payload = data.get("payload")
    if not isinstance(recipient, str) or not recipient:
        logger.warning("Agent message %s missing recipient", path)
        return None
    if not isinstance(message_type, str) or not message_type:
        logger.warning("Agent message %s missing message_type", path)
        return None
    if not isinstance(payload, dict):
        logger.warning("Agent message %s missing payload", path)
        return None

    sender = data.get("sender")
    sender_value = sender if isinstance(sender, str) else None
    raw_idempotency_key = data.get("idempotency_key")
    idempotency_key = (
        raw_idempotency_key
        if isinstance(raw_idempotency_key, str) and raw_idempotency_key
        else _build_agent_message_idempotency_key(
            recipient=recipient,
            sender=sender_value,
            message_type=message_type,
            payload=payload,
        )
    )
    queued_at = data.get("queued_at")
    queued_at_value = queued_at if isinstance(queued_at, (int, float)) else 0.0
    attempts = data.get("attempts")
    attempts_value = attempts if isinstance(attempts, int) and attempts >= 0 else 0
    next_attempt_at = data.get("next_attempt_at")
    next_attempt_at_value = (
        next_attempt_at if isinstance(next_attempt_at, (int, float)) else 0.0
    )
    return QueuedAgentMessage(
        path=path,
        recipient=recipient,
        sender=sender_value,
        message_type=message_type,
        payload=payload,
        idempotency_key=idempotency_key,
        queued_at=queued_at_value,
        attempts=attempts_value,
        next_attempt_at=next_attempt_at_value,
    )


def _build_suggestion_idempotency_key(payload_text: str) -> str:
    payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    return f"suggestion:{payload_hash}"


def _build_agent_message_idempotency_key(
    *,
    recipient: str,
    sender: str | None,
    message_type: str,
    payload: dict[str, Any],
) -> str:
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    material = f"{recipient}|{sender or ''}|{message_type}|{canonical_payload}"
    message_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"agent_message:{message_hash}"
