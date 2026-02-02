import asyncio
import json
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Protocol

from autogen_core import AgentId

from src.agents.messages import UserMessage


@dataclass(frozen=True)
class PendingQuestion:
    question_id: int
    content: str
    asked_by: str | None
    created_at: float


@dataclass(frozen=True)
class AnsweredQuestion:
    question_id: int
    content: str
    asked_by: str | None
    created_at: float
    answer: str
    answered_at: float


_pending_questions: list[PendingQuestion] = []
_answered_questions: list[AnsweredQuestion] = []
_pending_waiters: dict[int, asyncio.Future[str]] = {}
_pending_lock = threading.Lock()
_next_question_id = 1
_INBOX_STATE_FILE = Path("logs/cli_inbox.json")


def enqueue_pending_question(
    content: str,
    asked_by: str | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> int:
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
            )
        )
        if loop is not None:
            _pending_waiters[question_id] = loop.create_future()
        _store_inbox_state()
        return question_id


def get_pending_question() -> PendingQuestion | None:
    with _pending_lock:
        return _pending_questions[0] if _pending_questions else None


def get_pending_questions() -> list[PendingQuestion]:
    with _pending_lock:
        return list(_pending_questions)


def resolve_pending_question(answer: str) -> AnsweredQuestion | None:
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
        )
        _answered_questions.append(answered)
        future = _pending_waiters.pop(pending.question_id, None)
        if future and not future.done():
            future.set_result(answer)
        _store_inbox_state()
        return answered


def get_answered_questions() -> list[AnsweredQuestion]:
    with _pending_lock:
        return list(_answered_questions)


async def wait_for_answer(
    question_id: int, timeout_seconds: float | None = None
) -> str | None:
    with _pending_lock:
        future = _pending_waiters.get(question_id)
    if future is None:
        return None
    if timeout_seconds is None:
        return await future
    return await asyncio.wait_for(future, timeout_seconds)


def clear_pending_questions() -> None:
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
    state = _load_inbox_state()
    if state is None:
        return get_pending_questions()
    return [
        PendingQuestion(**payload)
        for payload in state.get("pending", [])
        if isinstance(payload, dict)
    ]


def list_inbox_answered_questions() -> list[AnsweredQuestion]:
    state = _load_inbox_state()
    if state is None:
        return get_answered_questions()
    return [
        AnsweredQuestion(**payload)
        for payload in state.get("answered", [])
        if isinstance(payload, dict)
    ]


def _load_inbox_state() -> dict[str, object] | None:
    if not _INBOX_STATE_FILE.exists():
        return None
    try:
        return json.loads(_INBOX_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _store_inbox_state() -> None:
    try:
        _INBOX_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pending": [asdict(item) for item in _pending_questions],
            "answered": [asdict(item) for item in _answered_questions],
            "next_question_id": _next_question_id,
            "updated_at": time.time(),
        }
        _INBOX_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


class MessageRuntime(Protocol):
    async def send_message(self, message: UserMessage, recipient: AgentId) -> None: ...


def _read_stdin(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[str],
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        pending_question = get_pending_question()
        if pending_question:
            print(f"Pending question (System4): {pending_question.content}", flush=True)
        try:
            line = input("User: ")
        except EOFError:
            loop.call_soon_threadsafe(stop_event.set)
            break
        if not line:
            continue
        loop.call_soon_threadsafe(queue.put_nowait, line)


async def read_stdin_loop(queue: asyncio.Queue[str], stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    await asyncio.to_thread(_read_stdin, loop, queue, stop_event)


async def forward_user_messages(
    queue: asyncio.Queue[str],
    runtime: MessageRuntime,
    recipient: AgentId,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            user_input = await queue.get()
        except asyncio.CancelledError:
            break
        if user_input.strip().lower() in {"/exit", "/quit"}:
            stop_event.set()
            continue
        message = UserMessage(content=user_input, source="User")
        await runtime.send_message(message=message, recipient=recipient)
