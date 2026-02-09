from __future__ import annotations

import json
import logging
import hashlib
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.cyberagent.core.paths import resolve_logs_path

logger = logging.getLogger(__name__)

SUGGEST_QUEUE_DIR = resolve_logs_path("suggest_queue")
SUGGEST_QUEUE_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class QueuedSuggestion:
    path: Path
    payload_text: str
    idempotency_key: str
    queued_at: float


def enqueue_suggestion(payload_text: str, idempotency_key: str | None = None) -> Path:
    """
    Persist a suggestion payload for the background runtime to process.

    Args:
        payload_text: Serialized payload to deliver to System4.

    Returns:
        Path to the queued payload file.
    """
    SUGGEST_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "payload_text": payload_text,
        "idempotency_key": idempotency_key
        or _build_suggestion_idempotency_key(payload_text),
        "queued_at": time.time(),
    }
    file_id = f"{time.time_ns()}_{uuid.uuid4().hex}"
    target = SUGGEST_QUEUE_DIR / f"{file_id}.json"
    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(target)
    return target


def read_queued_suggestions() -> list[QueuedSuggestion]:
    """
    Load queued suggestions in stable order without deleting them.
    """
    if not SUGGEST_QUEUE_DIR.exists():
        return []
    suggestions: list[QueuedSuggestion] = []
    for path in sorted(SUGGEST_QUEUE_DIR.glob("*.json")):
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


def ack_suggestion(path: Path) -> None:
    """
    Remove a suggestion payload after it has been processed.
    """
    try:
        path.unlink()
    except OSError as exc:
        logger.warning("Failed to remove suggestion %s: %s", path, exc)


def _build_suggestion_idempotency_key(payload_text: str) -> str:
    payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    return f"suggestion:{payload_hash}"
