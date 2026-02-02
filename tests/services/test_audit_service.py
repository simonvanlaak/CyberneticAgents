from __future__ import annotations

import logging

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
