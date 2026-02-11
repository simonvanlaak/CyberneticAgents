from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.cyberagent.cli import runtime_resume


def _init_resume_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE initiatives (id INTEGER PRIMARY KEY, team_id INTEGER, status TEXT)"
        )
        conn.execute(
            "CREATE TABLE tasks ("
            "id INTEGER PRIMARY KEY, "
            "team_id INTEGER, "
            "initiative_id INTEGER, "
            "status TEXT, "
            "assignee TEXT, "
            "name TEXT, "
            "content TEXT, "
            "result TEXT, "
            "reasoning TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE systems (id INTEGER PRIMARY KEY, team_id INTEGER, type TEXT, agent_id_str TEXT)"
        )
        conn.commit()
    finally:
        conn.close()


def test_queue_in_progress_initiatives_enqueues_messages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "resume.db"
    _init_resume_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO initiatives (id, team_id, status) VALUES (1, 7, 'in_progress')"
        )
        conn.execute(
            "INSERT INTO initiatives (id, team_id, status) VALUES (2, 7, 'pending')"
        )
        conn.execute(
            "INSERT INTO initiatives (id, team_id, status) VALUES (3, 7, 'in_progress')"
        )
        conn.execute(
            "INSERT INTO tasks (id, team_id, initiative_id, status) VALUES (10, 7, 2, 'pending')"
        )
        conn.execute(
            "INSERT INTO tasks (id, team_id, initiative_id, status, assignee) "
            "VALUES (11, 7, 2, 'completed', 'System1/root')"
        )
        conn.execute(
            "INSERT INTO tasks (id, team_id, initiative_id, status, assignee, reasoning) "
            "VALUES (12, 7, 1, 'blocked', 'System1/root', 'Ambiguous output')"
        )
        conn.execute(
            "INSERT INTO systems (id, team_id, type, agent_id_str) "
            "VALUES (1, 7, 'control', 'System3/root')"
        )
        conn.commit()
    finally:
        conn.close()

    recorded: list[dict[str, object]] = []
    monkeypatch.setattr(runtime_resume, "get_database_path", lambda: str(db_path))

    def _fake_enqueue(**kwargs: object) -> Path:
        recorded.append(dict(kwargs))
        return tmp_path / "queued.json"

    monkeypatch.setattr(runtime_resume, "enqueue_agent_message", _fake_enqueue)

    queued = runtime_resume.queue_in_progress_initiatives(team_id=7)

    assert queued == 5
    assert len(recorded) == 5
    assert recorded[0]["recipient"] == "System3/root"
    assert recorded[0]["message_type"] == "initiative_assign"
    assert recorded[0]["payload"] == {
        "initiative_id": 1,
        "source": "System4_root",
        "content": "Resume initiative 1.",
    }
    assert recorded[1]["payload"] == {
        "initiative_id": 2,
        "source": "System4_root",
        "content": "Resume initiative 2.",
    }
    assert recorded[2]["payload"] == {
        "initiative_id": 3,
        "source": "System4_root",
        "content": "Resume initiative 3.",
    }
    assert recorded[3]["message_type"] == "task_review"
    assert recorded[3]["sender"] == "System1/root"
    assert recorded[3]["payload"] == {
        "task_id": 11,
        "assignee_agent_id_str": "System1/root",
        "source": "System1_root",
        "content": "Review completed task 11.",
    }
    assert recorded[4]["message_type"] == "task_review"
    assert recorded[4]["sender"] == "System1/root"
    assert recorded[4]["payload"] == {
        "task_id": 12,
        "assignee_agent_id_str": "System1/root",
        "source": "System1_root",
        "content": "Ambiguous output",
    }


def test_queue_in_progress_initiatives_returns_zero_on_sql_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_resume, "get_database_path", lambda: "/does/not/exist.db"
    )

    queued = runtime_resume.queue_in_progress_initiatives(team_id=1)

    assert queued == 0


def test_queue_in_progress_initiatives_uses_fresh_idempotency_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "resume_idempotency.db"
    _init_resume_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO initiatives (id, team_id, status) VALUES (1, 7, 'in_progress')"
        )
        conn.execute(
            "INSERT INTO systems (id, team_id, type, agent_id_str) "
            "VALUES (1, 7, 'control', 'System3/root')"
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(runtime_resume, "get_database_path", lambda: str(db_path))
    recorded_keys: list[str] = []

    def _fake_enqueue(**kwargs: object) -> Path:
        key = kwargs.get("idempotency_key")
        assert isinstance(key, str)
        recorded_keys.append(key)
        return tmp_path / "queued.json"

    monkeypatch.setattr(runtime_resume, "enqueue_agent_message", _fake_enqueue)

    first = runtime_resume.queue_in_progress_initiatives(team_id=7)
    second = runtime_resume.queue_in_progress_initiatives(team_id=7)

    assert first == 1
    assert second == 1
    assert len(recorded_keys) == 2
    assert recorded_keys[0] != recorded_keys[1]
    assert recorded_keys[0].startswith("resume:team:7:initiative:1:")
    assert recorded_keys[1].startswith("resume:team:7:initiative:1:")
