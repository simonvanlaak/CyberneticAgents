from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.channels import inbox


def test_inbox_resolve_hydrates_from_persisted_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: resolve should hydrate from disk after restart.

    The dashboard reads pending questions from persisted state. If the process
    restarts, in-memory state may be empty while the state file still contains
    pending questions.
    """

    monkeypatch.setattr(inbox, "INBOX_STATE_FILE", tmp_path / "inbox.json")
    inbox.clear_pending_questions()

    inbox.enqueue_pending_question(
        "Need input?",
        asked_by="System4",
        channel="cli",
        session_id="cli-main",
    )

    # Simulate restart: keep state file but drop module globals.
    inbox._entries.clear()  # type: ignore[attr-defined]
    inbox._next_entry_id = 1  # type: ignore[attr-defined]

    pending = inbox.list_inbox_pending_questions(channel="cli", session_id="cli-main")
    assert len(pending) == 1

    resolved = inbox.resolve_pending_question("done", channel="cli", session_id="cli-main")
    assert resolved is not None
    assert resolved.answer == "done"
