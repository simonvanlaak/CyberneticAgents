from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.channels.telegram import session_store
from src.cyberagent.channels.telegram.parser import build_session_id


def _reset_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(session_store, "SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(session_store, "_loaded", False)
    monkeypatch.setattr(session_store, "_sessions", {})


def test_upsert_session_persists_and_updates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _reset_store(monkeypatch, tmp_path)

    session = session_store.upsert_session(
        chat_id=123,
        user_id=456,
        chat_type="private",
        user_info={"username": "alice", "first_name": "Alice"},
    )

    assert session.agent_session_id == build_session_id(123, 456)
    assert session.user_info["username"] == "alice"
    assert session.user_info["first_name"] == "Alice"
    assert session.chat_type == "private"

    updated = session_store.upsert_session(
        chat_id=123,
        user_id=456,
        chat_type="private",
        user_info={"last_name": "Smith"},
    )

    assert updated.agent_session_id == session.agent_session_id
    assert updated.user_info["username"] == "alice"
    assert updated.user_info["last_name"] == "Smith"
    assert updated.last_activity >= session.last_activity

    assert session_store.SESSIONS_FILE.exists()
    payload = session_store.SESSIONS_FILE.read_text(encoding="utf-8")
    assert '"sessions"' in payload


def test_session_store_loads_from_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _reset_store(monkeypatch, tmp_path)
    session_store.upsert_session(
        chat_id=1,
        user_id=2,
        chat_type="group",
        user_info={"username": "bob"},
    )
    session_id = build_session_id(1, 2)

    monkeypatch.setattr(session_store, "_loaded", False)
    monkeypatch.setattr(session_store, "_sessions", {})

    loaded = session_store.get_session(session_id)

    assert loaded is not None
    assert loaded.agent_session_id == session_id
    assert loaded.chat_type == "group"
    assert loaded.user_info["username"] == "bob"
