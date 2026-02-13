from __future__ import annotations

from src.github_stage_events import (
    extract_latest_stage_label_event,
    is_stage_ready_set_by_owner,
)


def test_extract_latest_stage_label_event_ignores_non_stage_labels() -> None:
    events = [
        {"event": "labeled", "label": {"name": "bug"}, "actor": {"login": "a"}},
        {"event": "labeled", "label": {"name": "stage:needs-clarification"}, "actor": {"login": "b"}},
    ]
    latest = extract_latest_stage_label_event(events)
    assert latest is not None
    assert latest.label_name == "stage:needs-clarification"
    assert latest.actor_login == "b"


def test_ready_must_be_latest_and_by_owner() -> None:
    events = [
        {"event": "labeled", "label": {"name": "stage:needs-clarification"}, "actor": {"login": "bot"}},
        {"event": "labeled", "label": {"name": "stage:ready-to-implement"}, "actor": {"login": "simonvanlaak"}},
    ]
    assert is_stage_ready_set_by_owner(events, owner_login="simonvanlaak") is True


def test_ready_set_by_non_owner_is_rejected() -> None:
    events = [
        {"event": "labeled", "label": {"name": "stage:ready-to-implement"}, "actor": {"login": "someone"}},
    ]
    assert is_stage_ready_set_by_owner(events, owner_login="simonvanlaak") is False


def test_latest_stage_event_must_be_ready() -> None:
    events = [
        {"event": "labeled", "label": {"name": "stage:ready-to-implement"}, "actor": {"login": "simonvanlaak"}},
        {"event": "labeled", "label": {"name": "stage:in-progress"}, "actor": {"login": "bot"}},
    ]
    assert is_stage_ready_set_by_owner(events, owner_login="simonvanlaak") is False
