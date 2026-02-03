from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.channels import inbox
from src.cyberagent.channels.routing import MessageRoute


def test_inbox_add_entry_records_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    entry = inbox.add_inbox_entry("user_prompt", "hello")
    entries = inbox.list_inbox_entries()

    assert entry.kind == "user_prompt"
    assert entry.channel == inbox.DEFAULT_CHANNEL
    assert entry.session_id == inbox.DEFAULT_SESSION_ID
    assert entries[0].content == "hello"


def test_inbox_list_entries_filters_by_kind_channel_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.add_inbox_entry(
        "user_prompt",
        "From telegram",
        channel="telegram",
        session_id="telegram:chat-1:user-2",
    )
    inbox.add_inbox_entry(
        "system_response",
        "From cli",
        channel="cli",
        session_id="cli-main",
    )
    inbox.enqueue_pending_question(
        "Need input?",
        asked_by="System4",
        channel="telegram",
        session_id="telegram:chat-1:user-2",
    )

    telegram_entries = inbox.list_inbox_entries(channel="telegram")
    assert len(telegram_entries) == 2
    assert {entry.kind for entry in telegram_entries} == {
        "user_prompt",
        "system_question",
    }

    system_questions = inbox.list_inbox_entries(kind="system_question")
    assert len(system_questions) == 1
    assert system_questions[0].content == "Need input?"

    cli_entries = inbox.list_inbox_entries(session_id="cli-main")
    assert len(cli_entries) == 1
    assert cli_entries[0].kind == "system_response"


def test_inbox_resolve_marks_question_answered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question("Need input?", asked_by="System4")
    resolved = inbox.resolve_pending_question("done")

    assert resolved is not None
    answered = inbox.list_inbox_entries(kind="system_question", status="answered")
    assert len(answered) == 1
    assert answered[0].answer == "done"


def test_inbox_resolve_for_route_blocks_cross_channel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question(
        "Telegram question",
        asked_by="System4",
        channel="telegram",
        session_id="telegram:chat-1:user-2",
    )

    resolved = inbox.resolve_pending_question_for_route(
        "cli answer",
        MessageRoute(channel="cli", session_id="cli-main"),
    )

    assert resolved is None
    pending = inbox.get_pending_question()
    assert pending is not None
    assert pending.content == "Telegram question"


def test_inbox_defaults_channel_and_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question("hello", asked_by="System4")
    pending = inbox.list_inbox_pending_questions()

    assert len(pending) == 1
    assert pending[0].channel == inbox.DEFAULT_CHANNEL
    assert pending[0].session_id == inbox.DEFAULT_SESSION_ID


def test_inbox_resolve_tracks_channel_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question(
        "Need input", asked_by="System4", channel="cli", session_id="cli-main"
    )
    answered = inbox.resolve_pending_question("done")

    assert answered is not None
    assert answered.channel == "cli"
    assert answered.session_id == "cli-main"
    assert answered.answer == "done"


def test_inbox_filters_by_channel_and_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question(
        "From telegram",
        asked_by="System4",
        channel="telegram",
        session_id="telegram:chat-1:user-2",
    )
    inbox.enqueue_pending_question(
        "From cli",
        asked_by="System4",
        channel="cli",
        session_id="cli-main",
    )

    pending = inbox.list_inbox_pending_questions(channel="telegram")
    assert len(pending) == 1
    assert pending[0].channel == "telegram"

    pending = inbox.list_inbox_pending_questions(session_id="cli-main")
    assert len(pending) == 1
    assert pending[0].session_id == "cli-main"


def test_inbox_answered_filters_by_channel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question(
        "Telegram question",
        asked_by="System4",
        channel="telegram",
        session_id="telegram:chat-9:user-9",
    )
    inbox.enqueue_pending_question(
        "CLI question",
        asked_by="System4",
        channel="cli",
        session_id="cli-main",
    )
    inbox.resolve_pending_question("telegram answer")
    inbox.resolve_pending_question("cli answer")

    answered = inbox.list_inbox_answered_questions(channel="telegram")
    assert len(answered) == 1
    assert answered[0].channel == "telegram"
