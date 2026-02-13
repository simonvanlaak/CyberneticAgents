from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.cyberagent.cli.runtime_queue_backend import (
    QueuedAgentMessage,
    build_runtime_queue_backend,
    default_sqlite_queue_path,
)
from src.cyberagent.core.paths import resolve_logs_path

AGENT_MESSAGE_QUEUE_DIR = resolve_logs_path("agent_message_queue")
AGENT_MESSAGE_DEAD_LETTER_DIR = resolve_logs_path("agent_message_dead_letter")


def enqueue_agent_message(
    *,
    recipient: str,
    sender: str | None,
    message_type: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
) -> Path:
    """Persist an agent message payload for the background runtime to process."""

    backend = _build_backend()
    return backend.enqueue_agent_message(
        recipient=recipient,
        sender=sender,
        message_type=message_type,
        payload=payload,
        idempotency_key=idempotency_key,
    )


def read_queued_agent_messages() -> list[QueuedAgentMessage]:
    """Load queued agent messages in stable order without deleting them."""

    backend = _build_backend()
    return backend.read_queued_agent_messages()


def ack_agent_message(path: Path) -> None:
    """Remove a queued agent message after it has been processed."""

    backend = _build_backend()
    backend.ack_agent_message(path)


def list_dead_letter_agent_messages() -> list[QueuedAgentMessage]:
    """Load dead-lettered agent messages in stable order."""

    backend = _build_backend()
    return backend.list_dead_letter_agent_messages()


def requeue_dead_letter_agent_message(path: Path) -> Path | None:
    """Move a dead-letter message back to the active queue for retry."""

    backend = _build_backend()
    return backend.requeue_dead_letter_agent_message(path)


def requeue_all_dead_letter_agent_messages(limit: int | None = None) -> int:
    """Requeue dead-letter messages up to ``limit`` entries."""

    moved = 0
    for message in list_dead_letter_agent_messages():
        if limit is not None and moved >= limit:
            break
        if requeue_dead_letter_agent_message(message.path) is not None:
            moved += 1
    return moved


def defer_agent_message(
    *,
    path: Path,
    error: str,
    now_ts: float | None = None,
    base_delay_seconds: float = 2.0,
    max_delay_seconds: float = 300.0,
    max_attempts: int = 8,
) -> bool:
    """Defer processing with exponential backoff.

    Returns True when the message is moved to dead-letter storage.
    """

    backend = _build_backend()
    return backend.defer_agent_message(
        path=path,
        error=error,
        now_ts=now_ts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        max_attempts=max_attempts,
    )


def _build_backend():
    backend_name = os.environ.get("CYBERAGENT_RUNTIME_QUEUE_BACKEND", "file")
    sqlite_path = Path(
        os.environ.get(
            "CYBERAGENT_RUNTIME_QUEUE_DB_PATH",
            str(default_sqlite_queue_path()),
        )
    )
    return build_runtime_queue_backend(
        backend=backend_name,
        suggest_queue_dir=resolve_logs_path("suggest_queue"),
        agent_message_queue_dir=AGENT_MESSAGE_QUEUE_DIR,
        agent_message_dead_letter_dir=AGENT_MESSAGE_DEAD_LETTER_DIR,
        sqlite_db_path=sqlite_path,
    )
