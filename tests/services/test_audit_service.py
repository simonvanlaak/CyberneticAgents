from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from src.cyberagent.services.audit import log_event


def test_log_event_emits_structured_audit(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="src.cyberagent.services.audit")

    log_event("audit_event", actor_id="system5/root", target_id=123)

    assert any(
        record.message == "audit_event"
        and record.__dict__.get("actor_id") == "system5/root"
        and record.__dict__.get("target_id") == 123
        for record in caplog.records
    )


def test_log_event_targets_named_logger(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="src.cyberagent.services.teams")

    log_event("audit_event", service="teams", actor_id="system5/root")

    assert any(
        record.message == "audit_event"
        and record.name == "src.cyberagent.services.teams"
        for record in caplog.records
    )


def test_log_event_persists_to_security_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "security_logs.db"
    monkeypatch.setenv("CYBERAGENT_SECURITY_LOG_DB_PATH", str(db_path))

    log_event("audit_event", actor_id="system5/root", target_id=123)

    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT event, level, service, timestamp, fields_json " "FROM audit_events"
        ).fetchall()

    assert len(rows) == 1
    event, level, service, timestamp, fields_json = rows[0]
    assert event == "audit_event"
    assert level == logging.INFO
    assert service == "audit"
    assert isinstance(timestamp, str)
    fields = json.loads(fields_json)
    assert fields["actor_id"] == "system5/root"
    assert fields["target_id"] == 123
