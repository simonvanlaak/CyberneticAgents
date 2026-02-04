from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENT_MESSAGE_QUEUE_DIR = Path("logs/agent_message_queue")


@dataclass(frozen=True)
class QueuedAgentMessage:
    path: Path
    recipient: str
    sender: str | None
    message_type: str
    payload: dict[str, Any]
    queued_at: float


def enqueue_agent_message(
    *,
    recipient: str,
    sender: str | None,
    message_type: str,
    payload: dict[str, Any],
) -> Path:
    """
    Persist an agent message payload for the background runtime to process.
    """
    AGENT_MESSAGE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    payload_data = {
        "recipient": recipient,
        "sender": sender,
        "message_type": message_type,
        "payload": payload,
        "queued_at": time.time(),
    }
    file_id = f"{time.time_ns()}_{uuid.uuid4().hex}"
    target = AGENT_MESSAGE_QUEUE_DIR / f"{file_id}.json"
    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload_data, indent=2), encoding="utf-8")
    tmp_path.replace(target)
    return target


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
        queued_at = data.get("queued_at")
        queued_at_value = queued_at if isinstance(queued_at, (int, float)) else 0.0
        messages.append(
            QueuedAgentMessage(
                path=path,
                recipient=recipient,
                sender=sender_value,
                message_type=message_type,
                payload=payload,
                queued_at=queued_at_value,
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
