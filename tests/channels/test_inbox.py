from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.channels import inbox


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
