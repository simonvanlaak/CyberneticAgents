from __future__ import annotations

from pathlib import Path

from src.cyberagent.cli import agent_message_queue


def test_defer_agent_message_sets_backoff_metadata(tmp_path: Path) -> None:
    agent_message_queue.AGENT_MESSAGE_QUEUE_DIR = tmp_path / "queue"
    agent_message_queue.AGENT_MESSAGE_DEAD_LETTER_DIR = tmp_path / "dead_letter"
    path = agent_message_queue.enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
    )

    dead_lettered = agent_message_queue.defer_agent_message(
        path=path,
        error="connection error",
        now_ts=100.0,
        base_delay_seconds=2.0,
        max_delay_seconds=10.0,
        max_attempts=5,
    )

    assert dead_lettered is False
    queued = agent_message_queue.read_queued_agent_messages()
    assert len(queued) == 1
    assert queued[0].idempotency_key
    assert queued[0].attempts == 1
    assert queued[0].next_attempt_at == 102.0


def test_defer_agent_message_moves_to_dead_letter_after_max_attempts(
    tmp_path: Path,
) -> None:
    agent_message_queue.AGENT_MESSAGE_QUEUE_DIR = tmp_path / "queue"
    agent_message_queue.AGENT_MESSAGE_DEAD_LETTER_DIR = tmp_path / "dead_letter"
    path = agent_message_queue.enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
    )

    dead_lettered = agent_message_queue.defer_agent_message(
        path=path,
        error="connection error",
        now_ts=100.0,
        base_delay_seconds=1.0,
        max_delay_seconds=8.0,
        max_attempts=1,
    )

    assert dead_lettered is True
    assert not path.exists()
    dead_letter_files = list(
        agent_message_queue.AGENT_MESSAGE_DEAD_LETTER_DIR.glob("*.json")
    )
    assert len(dead_letter_files) == 1


def test_enqueue_agent_message_accepts_explicit_idempotency_key(tmp_path: Path) -> None:
    agent_message_queue.AGENT_MESSAGE_QUEUE_DIR = tmp_path / "queue"
    path = agent_message_queue.enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
        idempotency_key="resume:initiative:1",
    )

    queued = agent_message_queue.read_queued_agent_messages()
    assert path.exists()
    assert len(queued) == 1
    assert queued[0].idempotency_key == "resume:initiative:1"
