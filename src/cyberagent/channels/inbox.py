from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CHANNEL = "cli"
DEFAULT_SESSION_ID = "cli-main"
INBOX_STATE_FILE = Path("logs/cli_inbox.json")


@dataclass(frozen=True)
class PendingQuestion:
    question_id: int
    content: str
    asked_by: str | None
    created_at: float
    channel: str = DEFAULT_CHANNEL
    session_id: str = DEFAULT_SESSION_ID


@dataclass(frozen=True)
class AnsweredQuestion:
    question_id: int
    content: str
    asked_by: str | None
    created_at: float
    answer: str
    answered_at: float
    channel: str = DEFAULT_CHANNEL
    session_id: str = DEFAULT_SESSION_ID


_pending_questions: list[PendingQuestion] = []
_answered_questions: list[AnsweredQuestion] = []
_pending_waiters: dict[int, asyncio.Future[str]] = {}
_pending_lock = threading.Lock()
_next_question_id = 1


def enqueue_pending_question(
    content: str,
    asked_by: str | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
    channel: str = DEFAULT_CHANNEL,
    session_id: str = DEFAULT_SESSION_ID,
) -> int:
    """Record a pending question for the inbox."""
    global _next_question_id
    with _pending_lock:
        question_id = _next_question_id
        _next_question_id += 1
        _pending_questions.append(
            PendingQuestion(
                question_id=question_id,
                content=content,
                asked_by=asked_by,
                created_at=time.time(),
                channel=channel,
                session_id=session_id,
            )
        )
        if loop is not None:
            _pending_waiters[question_id] = loop.create_future()
        _store_inbox_state()
        return question_id


def get_pending_question() -> PendingQuestion | None:
    """Return the oldest pending question, if any."""
    with _pending_lock:
        return _pending_questions[0] if _pending_questions else None


def get_pending_questions() -> list[PendingQuestion]:
    """Return all pending questions."""
    with _pending_lock:
        return list(_pending_questions)


def resolve_pending_question(answer: str) -> AnsweredQuestion | None:
    """Resolve the oldest pending question with the provided answer."""
    with _pending_lock:
        if not _pending_questions:
            return None
        pending = _pending_questions.pop(0)
        answered = AnsweredQuestion(
            question_id=pending.question_id,
            content=pending.content,
            asked_by=pending.asked_by,
            created_at=pending.created_at,
            answer=answer,
            answered_at=time.time(),
            channel=pending.channel,
            session_id=pending.session_id,
        )
        _answered_questions.append(answered)
        future = _pending_waiters.pop(pending.question_id, None)
        if future and not future.done():
            future.set_result(answer)
        _store_inbox_state()
        return answered


def get_answered_questions() -> list[AnsweredQuestion]:
    """Return all answered questions."""
    with _pending_lock:
        return list(_answered_questions)


async def wait_for_answer(
    question_id: int, timeout_seconds: float | None = None
) -> str | None:
    """Wait for a specific pending question to be answered."""
    with _pending_lock:
        future = _pending_waiters.get(question_id)
    if future is None:
        return None
    if timeout_seconds is None:
        return await future
    return await asyncio.wait_for(future, timeout_seconds)


def clear_pending_questions() -> None:
    """Clear inbox state (used primarily for tests)."""
    global _next_question_id
    with _pending_lock:
        for future in _pending_waiters.values():
            if not future.done():
                future.cancel()
        _pending_waiters.clear()
        _pending_questions.clear()
        _answered_questions.clear()
        _next_question_id = 1
        _store_inbox_state()


def list_inbox_pending_questions() -> list[PendingQuestion]:
    """List pending questions from persisted inbox state."""
    state = _load_inbox_state()
    if state is None:
        return get_pending_questions()
    pending = state.get("pending")
    if not isinstance(pending, list):
        return get_pending_questions()
    return [
        PendingQuestion(**payload) for payload in pending if isinstance(payload, dict)
    ]


def list_inbox_answered_questions() -> list[AnsweredQuestion]:
    """List answered questions from persisted inbox state."""
    state = _load_inbox_state()
    if state is None:
        return get_answered_questions()
    answered = state.get("answered")
    if not isinstance(answered, list):
        return get_answered_questions()
    return [
        AnsweredQuestion(**payload) for payload in answered if isinstance(payload, dict)
    ]


def _load_inbox_state() -> dict[str, object] | None:
    if not INBOX_STATE_FILE.exists():
        return None
    try:
        return json.loads(INBOX_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _store_inbox_state() -> None:
    try:
        INBOX_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pending": [asdict(item) for item in _pending_questions],
            "answered": [asdict(item) for item in _answered_questions],
            "next_question_id": _next_question_id,
            "updated_at": time.time(),
        }
        INBOX_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return
