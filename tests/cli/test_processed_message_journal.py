from pathlib import Path

from src.cyberagent.cli import processed_message_journal as journal


def test_mark_processed_message_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(journal, "JOURNAL_DIR", tmp_path)
    assert journal.was_processed_message("agent_message", "k1") is False

    journal.mark_processed_message("agent_message", "k1")

    assert journal.was_processed_message("agent_message", "k1") is True


def test_mark_processed_message_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(journal, "JOURNAL_DIR", tmp_path)
    journal.mark_processed_message("agent_message", "k1")
    journal.mark_processed_message("agent_message", "k1")

    journal_path = tmp_path / "agent_message.jsonl"
    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
