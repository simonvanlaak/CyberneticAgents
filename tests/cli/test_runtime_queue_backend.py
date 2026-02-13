from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from src.cyberagent.cli.runtime_queue_backend import (
    FileRuntimeQueueBackend,
    RuntimeQueueBackend,
    SQLiteRuntimeQueueBackend,
)


def _build_file_backend(tmp_path: Path) -> RuntimeQueueBackend:
    return FileRuntimeQueueBackend(
        suggest_queue_dir=tmp_path / "suggest_queue",
        agent_message_queue_dir=tmp_path / "agent_queue",
        agent_message_dead_letter_dir=tmp_path / "agent_dead_letter",
    )


def _build_sqlite_backend(tmp_path: Path) -> RuntimeQueueBackend:
    return SQLiteRuntimeQueueBackend(db_path=tmp_path / "runtime_queue.db")


@pytest.mark.parametrize(
    "factory",
    [_build_file_backend, _build_sqlite_backend],
    ids=["file", "sqlite"],
)
def test_runtime_queue_backend_suggestion_contract(
    tmp_path: Path,
    factory: Callable[[Path], RuntimeQueueBackend],
) -> None:
    backend = factory(tmp_path)

    backend.enqueue_suggestion("first")
    backend.enqueue_suggestion("second")

    queued = backend.read_queued_suggestions()
    assert [item.payload_text for item in queued] == ["first", "second"]
    assert queued[0].idempotency_key
    assert queued[1].idempotency_key

    backend.ack_suggestion(queued[0].path)

    remaining = backend.read_queued_suggestions()
    assert [item.payload_text for item in remaining] == ["second"]


@pytest.mark.parametrize(
    "factory",
    [_build_file_backend, _build_sqlite_backend],
    ids=["file", "sqlite"],
)
def test_runtime_queue_backend_agent_message_contract(
    tmp_path: Path,
    factory: Callable[[Path], RuntimeQueueBackend],
) -> None:
    backend = factory(tmp_path)

    first = backend.enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
        idempotency_key="resume:initiative:1",
    )
    second = backend.enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
        idempotency_key="resume:initiative:1",
    )

    assert first == second

    queued = backend.read_queued_agent_messages()
    assert len(queued) == 1
    assert queued[0].idempotency_key == "resume:initiative:1"

    dead_lettered = backend.defer_agent_message(
        path=queued[0].path,
        error="network error",
        now_ts=10.0,
        base_delay_seconds=2.0,
        max_delay_seconds=10.0,
        max_attempts=5,
    )
    assert dead_lettered is False

    deferred = backend.read_queued_agent_messages()
    assert len(deferred) == 1
    assert deferred[0].attempts == 1
    assert deferred[0].next_attempt_at == 12.0

    dead_lettered = backend.defer_agent_message(
        path=deferred[0].path,
        error="network error",
        now_ts=10.0,
        max_attempts=1,
    )
    assert dead_lettered is True
    assert not backend.read_queued_agent_messages()

    dead_letters = backend.list_dead_letter_agent_messages()
    assert len(dead_letters) == 1

    requeued = backend.requeue_dead_letter_agent_message(dead_letters[0].path)
    assert requeued is not None

    replay = backend.read_queued_agent_messages()
    assert len(replay) == 1
    assert replay[0].attempts == 0
