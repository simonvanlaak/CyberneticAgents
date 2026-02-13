from __future__ import annotations

import os
from pathlib import Path

from src.cyberagent.cli.runtime_queue_backend import (
    QueuedSuggestion,
    build_runtime_queue_backend,
    default_sqlite_queue_path,
)
from src.cyberagent.core.paths import resolve_logs_path

SUGGEST_QUEUE_DIR = resolve_logs_path("suggest_queue")
SUGGEST_QUEUE_POLL_SECONDS = 0.5


def enqueue_suggestion(payload_text: str, idempotency_key: str | None = None) -> Path:
    """Persist a suggestion payload for the background runtime to process."""

    backend = _build_backend()
    return backend.enqueue_suggestion(payload_text, idempotency_key=idempotency_key)


def read_queued_suggestions() -> list[QueuedSuggestion]:
    """Load queued suggestions in stable order without deleting them."""

    backend = _build_backend()
    return backend.read_queued_suggestions()


def ack_suggestion(path: Path) -> None:
    """Remove a suggestion payload after it has been processed."""

    backend = _build_backend()
    backend.ack_suggestion(path)


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
        suggest_queue_dir=SUGGEST_QUEUE_DIR,
        agent_message_queue_dir=resolve_logs_path("agent_message_queue"),
        agent_message_dead_letter_dir=resolve_logs_path("agent_message_dead_letter"),
        sqlite_db_path=sqlite_path,
    )
