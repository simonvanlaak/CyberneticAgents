from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.cyberagent.channels.telegram.parser import build_session_id

SESSIONS_FILE = Path("logs/telegram_sessions.json")
_lock = threading.Lock()
_loaded = False
_sessions: dict[str, TelegramSession] = {}


@dataclass
class TelegramSession:
    telegram_user_id: int
    telegram_chat_id: int
    agent_session_id: str
    user_info: dict[str, Any]
    chat_type: str | None
    created_at: float
    last_activity: float
    context: dict[str, Any] = field(default_factory=dict)


def upsert_session(
    chat_id: int,
    user_id: int,
    chat_type: str | None,
    user_info: dict[str, Any],
) -> TelegramSession:
    _ensure_loaded()
    session_id = build_session_id(chat_id, user_id)
    now = time.time()
    with _lock:
        existing = _sessions.get(session_id)
        if existing:
            existing.last_activity = now
            if chat_type:
                existing.chat_type = chat_type
            if user_info:
                existing.user_info.update({k: v for k, v in user_info.items() if v})
            _store()
            return existing
        session = TelegramSession(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            agent_session_id=session_id,
            user_info={k: v for k, v in user_info.items() if v},
            chat_type=chat_type,
            created_at=now,
            last_activity=now,
        )
        _sessions[session_id] = session
        _store()
        return session


def get_session(session_id: str) -> TelegramSession | None:
    _ensure_loaded()
    with _lock:
        return _sessions.get(session_id)


def list_sessions() -> list[TelegramSession]:
    _ensure_loaded()
    with _lock:
        return list(_sessions.values())


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        if not SESSIONS_FILE.exists():
            _loaded = True
            return
        try:
            payload = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _loaded = True
            return
        sessions_raw = payload.get("sessions") if isinstance(payload, dict) else None
        if isinstance(sessions_raw, dict):
            for session_id, raw in sessions_raw.items():
                if isinstance(raw, dict):
                    _sessions[session_id] = _from_dict(raw)
        _loaded = True


def _store() -> None:
    try:
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": {sid: asdict(session) for sid, session in _sessions.items()},
            "updated_at": time.time(),
        }
        SESSIONS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def _from_dict(raw: dict[str, Any]) -> TelegramSession:
    return TelegramSession(
        telegram_user_id=int(raw.get("telegram_user_id", 0)),
        telegram_chat_id=int(raw.get("telegram_chat_id", 0)),
        agent_session_id=str(raw.get("agent_session_id", "")),
        user_info=dict(raw.get("user_info") or {}),
        chat_type=raw.get("chat_type"),
        created_at=float(raw.get("created_at", 0)),
        last_activity=float(raw.get("last_activity", 0)),
        context=dict(raw.get("context") or {}),
    )
