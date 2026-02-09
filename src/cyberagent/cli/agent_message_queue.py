from __future__ import annotations

import json
import logging
import hashlib
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.cyberagent.core.paths import resolve_logs_path

logger = logging.getLogger(__name__)

AGENT_MESSAGE_QUEUE_DIR = resolve_logs_path("agent_message_queue")
AGENT_MESSAGE_DEAD_LETTER_DIR = resolve_logs_path("agent_message_dead_letter")


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


def enqueue_agent_message(
    *,
    recipient: str,
    sender: str | None,
    message_type: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
) -> Path:
    """
    Persist an agent message payload for the background runtime to process.
    """
    AGENT_MESSAGE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    resolved_idempotency_key = idempotency_key or _build_agent_message_idempotency_key(
        recipient=recipient,
        sender=sender,
        message_type=message_type,
        payload=payload,
    )
    existing_path = _find_queued_message_by_idempotency_key(resolved_idempotency_key)
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
    target = AGENT_MESSAGE_QUEUE_DIR / f"{file_id}.json"
    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload_data, indent=2), encoding="utf-8")
    tmp_path.replace(target)
    return target


def _find_queued_message_by_idempotency_key(idempotency_key: str) -> Path | None:
    if not AGENT_MESSAGE_QUEUE_DIR.exists():
        return None
    for path in sorted(AGENT_MESSAGE_QUEUE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        queued_key = data.get("idempotency_key")
        if queued_key == idempotency_key:
            return path
    return None


def read_queued_agent_messages() -> list[QueuedAgentMessage]:
    """
    Load queued agent messages in stable order without deleting them.
    """
    if not AGENT_MESSAGE_QUEUE_DIR.exists():
        return []
    messages: list[QueuedAgentMessage] = []
    for path in sorted(AGENT_MESSAGE_QUEUE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read agent message %s: %s", path, exc)
            continue
        recipient = data.get("recipient")
        message_type = data.get("message_type")
        payload = data.get("payload")
        if not isinstance(recipient, str) or not recipient:
            logger.warning("Agent message %s missing recipient", path)
            continue
        if not isinstance(message_type, str) or not message_type:
            logger.warning("Agent message %s missing message_type", path)
            continue
        if not isinstance(payload, dict):
            logger.warning("Agent message %s missing payload", path)
            continue
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
        messages.append(
            QueuedAgentMessage(
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
        )
    return messages


def ack_agent_message(path: Path) -> None:
    """
    Remove a queued agent message after it has been processed.
    """
    try:
        path.unlink()
    except OSError as exc:
        logger.warning("Failed to remove agent message %s: %s", path, exc)


def list_dead_letter_agent_messages() -> list[QueuedAgentMessage]:
    """
    Load dead-lettered agent messages in stable order.
    """
    if not AGENT_MESSAGE_DEAD_LETTER_DIR.exists():
        return []
    messages: list[QueuedAgentMessage] = []
    for path in sorted(AGENT_MESSAGE_DEAD_LETTER_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read dead-letter message %s: %s", path, exc)
            continue
        recipient = data.get("recipient")
        message_type = data.get("message_type")
        payload = data.get("payload")
        if not isinstance(recipient, str) or not recipient:
            continue
        if not isinstance(message_type, str) or not message_type:
            continue
        if not isinstance(payload, dict):
            continue
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
        messages.append(
            QueuedAgentMessage(
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
        )
    return messages


def requeue_dead_letter_agent_message(path: Path) -> Path | None:
    """
    Move a dead-letter message back to the active queue for retry.
    """
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
    AGENT_MESSAGE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    target = AGENT_MESSAGE_QUEUE_DIR / path.name
    try:
        tmp_path = target.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(target)
        path.unlink(missing_ok=True)
        return target
    except OSError as exc:
        logger.warning("Failed to requeue dead-letter message %s: %s", path, exc)
        return None


def requeue_all_dead_letter_agent_messages(limit: int | None = None) -> int:
    """
    Requeue dead-letter messages up to ``limit`` entries.
    """
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
    """
    Defer processing with exponential backoff.

    Returns True when the message is moved to dead-letter storage.
    """
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
        AGENT_MESSAGE_DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
        target = AGENT_MESSAGE_DEAD_LETTER_DIR / path.name
        data["dead_lettered_at"] = timestamp
        try:
            tmp_path = target.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(target)
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
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(path)
    except OSError as exc:
        logger.warning("Failed to update deferred agent message %s: %s", path, exc)
    return False


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
