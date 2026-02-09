from __future__ import annotations

import json
import time
from pathlib import Path

from src.cyberagent.core.paths import resolve_logs_path

JOURNAL_DIR = resolve_logs_path("queue_journal")


def was_processed_message(scope: str, idempotency_key: str) -> bool:
    """
    Return True when an idempotency key is already present in the journal.
    """
    journal_path = _journal_path(scope)
    if not journal_path.exists():
        return False
    try:
        with journal_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("idempotency_key") == idempotency_key:
                    return True
    except OSError:
        return False
    return False


def mark_processed_message(scope: str, idempotency_key: str) -> None:
    """
    Append a processed idempotency marker to the journal.
    """
    if was_processed_message(scope, idempotency_key):
        return
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    journal_path = _journal_path(scope)
    entry = {
        "idempotency_key": idempotency_key,
        "recorded_at": time.time(),
    }
    with journal_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True))
        handle.write("\n")


def _journal_path(scope: str) -> Path:
    safe_scope = "".join(
        ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in scope
    )
    return JOURNAL_DIR / f"{safe_scope}.jsonl"
