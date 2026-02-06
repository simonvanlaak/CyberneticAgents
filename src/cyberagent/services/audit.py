"""Shared audit logging helpers."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Dict

from src.cyberagent.core.paths import resolve_data_path

_AUDIT_DB_ENV = "CYBERAGENT_SECURITY_LOG_DB_PATH"
_DEFAULT_AUDIT_DB_PATH = resolve_data_path("security_logs.db")
_AUDIT_TABLE = "audit_events"


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """
    Emit a structured audit event.

    Args:
        event: Event name.
        **fields: Structured metadata for the event.
    """
    service = str(fields.get("service", "audit"))
    logger = logging.getLogger(f"src.cyberagent.services.{service}")
    extra = dict(fields)
    extra.pop("service", None)
    extra.setdefault(
        "timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    logger.log(level, event, extra=extra)
    _persist_audit_event(event=event, level=level, service=service, fields=extra)


def _persist_audit_event(
    *, event: str, level: int, service: str, fields: Dict[str, Any]
) -> None:
    path = _get_audit_db_path()
    try:
        _ensure_audit_db(path)
        timestamp = fields.get(
            "timestamp",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        payload = json.dumps(fields, default=str)
        with sqlite3.connect(path) as conn:
            conn.execute(
                f"INSERT INTO {_AUDIT_TABLE} "
                "(event, level, service, timestamp, fields_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (event, level, service, timestamp, payload),
            )
            conn.commit()
    except sqlite3.Error as exc:
        logger = logging.getLogger("src.cyberagent.services.audit")
        logger.warning("Failed to persist audit event: %s", exc)


def _ensure_audit_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_AUDIT_TABLE} ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event TEXT NOT NULL, "
            "level INTEGER NOT NULL, "
            "service TEXT NOT NULL, "
            "timestamp TEXT NOT NULL, "
            "fields_json TEXT NOT NULL"
            ")"
        )
        conn.commit()


def _get_audit_db_path() -> Path:
    raw_path = os.getenv(_AUDIT_DB_ENV)
    if raw_path:
        return Path(raw_path)
    return _DEFAULT_AUDIT_DB_PATH
