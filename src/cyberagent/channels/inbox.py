from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import asdict, dataclass, replace
from typing import Literal, TypeVar

from src.cyberagent.channels.routing import MessageRoute, is_reply_route_allowed
from src.cyberagent.core.paths import resolve_logs_path

DEFAULT_CHANNEL = "cli"
DEFAULT_SESSION_ID = "cli-main"
INBOX_STATE_FILE = resolve_logs_path("cli_inbox.json")

InboxEntryKind = Literal["user_prompt", "system_question", "system_response"]
InboxEntryStatus = Literal["pending", "answered"]


@dataclass(frozen=True)
class InboxEntry:
    entry_id: int
    kind: InboxEntryKind
    content: str
    created_at: float
    channel: str = DEFAULT_CHANNEL
    session_id: str = DEFAULT_SESSION_ID
    asked_by: str | None = None
    status: InboxEntryStatus | None = None
    answered_at: float | None = None
    answer: str | None = None
    metadata: dict[str, str] | None = None


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


_entries: list[InboxEntry] = []
_pending_waiters: dict[int, asyncio.Future[str]] = {}
_pending_lock = threading.Lock()
_next_entry_id = 1


def _ensure_inbox_loaded() -> None:
    """Hydrate in-memory inbox state from disk on first use.

    Some read paths (e.g. the dashboard) intentionally read from persisted state.
    If the process restarts, `_entries` may be empty while the state file still
    contains pending questions; resolving should still work.
    """
    global _entries, _next_entry_id
    if _entries:
        return
    state = _load_inbox_state()
    if state is None:
        return
    try:
        entries = _entries_from_state(state)
        next_entry_id = int(state.get("next_entry_id", len(entries) + 1))
    except Exception:
        return
    _entries = entries
    _next_entry_id = max(next_entry_id, len(entries) + 1)


def add_inbox_entry(
    kind: InboxEntryKind,
    content: str,
    *,
    channel: str = DEFAULT_CHANNEL,
    session_id: str = DEFAULT_SESSION_ID,
    asked_by: str | None = None,
    status: InboxEntryStatus | None = None,
    answer: str | None = None,
    answered_at: float | None = None,
    metadata: dict[str, str] | None = None,
) -> InboxEntry:
    """Add a new inbox entry."""
    with _pending_lock:
        _ensure_inbox_loaded()
        entry = _add_inbox_entry_locked(
            kind=kind,
            content=content,
            channel=channel,
            session_id=session_id,
            asked_by=asked_by,
            status=status,
            answered_at=answered_at,
            answer=answer,
            metadata=metadata,
        )
        _store_inbox_state()
        return entry


def enqueue_pending_question(
    content: str,
    asked_by: str | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
    channel: str = DEFAULT_CHANNEL,
    session_id: str = DEFAULT_SESSION_ID,
) -> int:
    """Record a pending question for the inbox."""
    with _pending_lock:
        _ensure_inbox_loaded()
        entry = _add_inbox_entry_locked(
            kind="system_question",
            content=content,
            channel=channel,
            session_id=session_id,
            asked_by=asked_by,
            status="pending",
        )
        if loop is not None:
            _pending_waiters[entry.entry_id] = loop.create_future()
        _store_inbox_state()
        return entry.entry_id


def get_pending_question(
    channel: str | None = None,
    session_id: str | None = None,
) -> PendingQuestion | None:
    """Return the oldest pending question, if any."""
    entry = _get_pending_entry(channel=channel, session_id=session_id)
    if entry is None:
        return None
    return _pending_question_from_entry(entry)


def get_pending_questions(
    channel: str | None = None,
    session_id: str | None = None,
) -> list[PendingQuestion]:
    """Return all pending questions."""
    entries = _get_pending_entries(channel=channel, session_id=session_id)
    return [_pending_question_from_entry(entry) for entry in entries]


def resolve_pending_question(
    answer: str, channel: str | None = None, session_id: str | None = None
) -> AnsweredQuestion | None:
    """Resolve the oldest pending question with the provided answer."""
    with _pending_lock:
        _ensure_inbox_loaded()
        entry_index = _get_pending_entry_index(channel=channel, session_id=session_id)
        if entry_index is None:
            return None
        pending = _entries[entry_index]
        updated = replace(
            pending,
            status="answered",
            answered_at=time.time(),
            answer=answer,
        )
        _entries[entry_index] = updated
        future = _pending_waiters.pop(pending.entry_id, None)
        if future and not future.done():
            future.set_result(answer)
        _store_inbox_state()
        return _answered_question_from_entry(updated)


def resolve_pending_question_for_route(
    answer: str, reply_route: MessageRoute
) -> AnsweredQuestion | None:
    """
    Resolve the oldest pending question only if the reply route matches.

    Args:
        answer: User-provided answer.
        reply_route: Routing info for the reply attempt.

    Returns:
        AnsweredQuestion when routing is allowed; otherwise None.
    """
    pending = get_pending_question()
    if pending is None:
        return None
    origin = MessageRoute(channel=pending.channel, session_id=pending.session_id)
    if not is_reply_route_allowed(origin, reply_route):
        return None
    return resolve_pending_question(
        answer, channel=reply_route.channel, session_id=reply_route.session_id
    )


def get_answered_questions() -> list[AnsweredQuestion]:
    """Return all answered questions."""
    entries = _get_answered_entries()
    return [_answered_question_from_entry(entry) for entry in entries]


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
    global _next_entry_id
    with _pending_lock:
        for future in _pending_waiters.values():
            if not future.done():
                future.cancel()
        _pending_waiters.clear()
        _entries.clear()
        _next_entry_id = 1
        _store_inbox_state()


def list_inbox_pending_questions(
    channel: str | None = None,
    session_id: str | None = None,
) -> list[PendingQuestion]:
    """List pending questions from persisted inbox state."""
    state = _load_inbox_state()
    if state is None:
        return _filter_inbox_entries(get_pending_questions(), channel, session_id)
    entries = _entries_from_state(state)
    pending = [entry for entry in entries if _is_pending_question(entry)]
    return [
        _pending_question_from_entry(entry)
        for entry in _filter_inbox_entries(pending, channel, session_id)
    ]


def list_inbox_answered_questions(
    channel: str | None = None,
    session_id: str | None = None,
) -> list[AnsweredQuestion]:
    """List answered questions from persisted inbox state."""
    state = _load_inbox_state()
    if state is None:
        return _filter_inbox_entries(get_answered_questions(), channel, session_id)
    entries = _entries_from_state(state)
    answered = [entry for entry in entries if _is_answered_question(entry)]
    return [
        _answered_question_from_entry(entry)
        for entry in _filter_inbox_entries(answered, channel, session_id)
    ]


def list_inbox_entries(
    *,
    kind: InboxEntryKind | None = None,
    status: InboxEntryStatus | None = None,
    channel: str | None = None,
    session_id: str | None = None,
) -> list[InboxEntry]:
    """List inbox entries from persisted state."""
    state = _load_inbox_state()
    if state is None:
        return _filter_entries(
            list(_entries),
            kind=kind,
            status=status,
            channel=channel,
            session_id=session_id,
        )
    entries = _entries_from_state(state)
    return _filter_entries(
        entries,
        kind=kind,
        status=status,
        channel=channel,
        session_id=session_id,
    )


TInboxEntry = TypeVar("TInboxEntry")


def _filter_inbox_entries(
    entries: list[TInboxEntry],
    channel: str | None,
    session_id: str | None,
) -> list[TInboxEntry]:
    if not channel and not session_id:
        return entries
    filtered: list[TInboxEntry] = []
    for entry in entries:
        entry_channel = getattr(entry, "channel", None)
        entry_session_id = getattr(entry, "session_id", None)
        if channel and entry_channel != channel:
            continue
        if session_id and entry_session_id != session_id:
            continue
        filtered.append(entry)
    return filtered


def _filter_entries(
    entries: list[InboxEntry],
    *,
    kind: InboxEntryKind | None,
    status: InboxEntryStatus | None,
    channel: str | None,
    session_id: str | None,
) -> list[InboxEntry]:
    filtered: list[InboxEntry] = []
    for entry in entries:
        if kind and entry.kind != kind:
            continue
        if status and entry.status != status:
            continue
        if channel and entry.channel != channel:
            continue
        if session_id and entry.session_id != session_id:
            continue
        filtered.append(entry)
    return filtered


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
            "entries": [asdict(item) for item in _entries],
            "next_entry_id": _next_entry_id,
            "updated_at": time.time(),
        }
        INBOX_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def _add_inbox_entry_locked(
    *,
    kind: InboxEntryKind,
    content: str,
    channel: str,
    session_id: str,
    asked_by: str | None,
    status: InboxEntryStatus | None,
    answer: str | None = None,
    answered_at: float | None = None,
    metadata: dict[str, str] | None = None,
) -> InboxEntry:
    global _next_entry_id
    entry = InboxEntry(
        entry_id=_next_entry_id,
        kind=kind,
        content=content,
        created_at=time.time(),
        channel=channel,
        session_id=session_id,
        asked_by=asked_by,
        status=status,
        answered_at=answered_at,
        answer=answer,
        metadata=metadata,
    )
    _next_entry_id += 1
    _entries.append(entry)
    return entry


def _get_pending_entries(
    channel: str | None = None,
    session_id: str | None = None,
) -> list[InboxEntry]:
    with _pending_lock:
        _ensure_inbox_loaded()
        entries = [entry for entry in _entries if _is_pending_question(entry)]
    return _filter_entries(
        entries,
        kind="system_question",
        status="pending",
        channel=channel,
        session_id=session_id,
    )


def _get_answered_entries() -> list[InboxEntry]:
    with _pending_lock:
        _ensure_inbox_loaded()
        return [entry for entry in _entries if _is_answered_question(entry)]


def _get_pending_entry(
    channel: str | None = None,
    session_id: str | None = None,
) -> InboxEntry | None:
    entries = _get_pending_entries(channel=channel, session_id=session_id)
    return entries[0] if entries else None


def _get_pending_entry_index(
    channel: str | None = None,
    session_id: str | None = None,
) -> int | None:
    for index, entry in enumerate(_entries):
        if not _is_pending_question(entry):
            continue
        if channel and entry.channel != channel:
            continue
        if session_id and entry.session_id != session_id:
            continue
        return index
    return None


def _pending_question_from_entry(entry: InboxEntry) -> PendingQuestion:
    return PendingQuestion(
        question_id=entry.entry_id,
        content=entry.content,
        asked_by=entry.asked_by,
        created_at=entry.created_at,
        channel=entry.channel,
        session_id=entry.session_id,
    )


def _answered_question_from_entry(entry: InboxEntry) -> AnsweredQuestion:
    return AnsweredQuestion(
        question_id=entry.entry_id,
        content=entry.content,
        asked_by=entry.asked_by,
        created_at=entry.created_at,
        answer=entry.answer or "",
        answered_at=entry.answered_at or entry.created_at,
        channel=entry.channel,
        session_id=entry.session_id,
    )


def _is_pending_question(entry: InboxEntry) -> bool:
    return entry.kind == "system_question" and entry.status == "pending"


def _is_answered_question(entry: InboxEntry) -> bool:
    return entry.kind == "system_question" and entry.status == "answered"


def _entries_from_state(state: dict[str, object]) -> list[InboxEntry]:
    entries = state.get("entries")
    if isinstance(entries, list):
        return [
            InboxEntry(**payload) for payload in entries if isinstance(payload, dict)
        ]
    return _entries_from_legacy_state(state)


def _entries_from_legacy_state(state: dict[str, object]) -> list[InboxEntry]:
    pending_raw = state.get("pending")
    answered_raw = state.get("answered")
    entries: list[InboxEntry] = []
    max_id = 0
    if isinstance(pending_raw, list):
        for payload in pending_raw:
            if not isinstance(payload, dict):
                continue
            question_id = int(payload.get("question_id", 0))
            if question_id <= 0:
                continue
            max_id = max(max_id, question_id)
            entries.append(
                InboxEntry(
                    entry_id=question_id,
                    kind="system_question",
                    content=str(payload.get("content", "")),
                    created_at=float(payload.get("created_at", 0)),
                    channel=str(payload.get("channel", DEFAULT_CHANNEL)),
                    session_id=str(payload.get("session_id", DEFAULT_SESSION_ID)),
                    asked_by=payload.get("asked_by"),
                    status="pending",
                )
            )
    if isinstance(answered_raw, list):
        for payload in answered_raw:
            if not isinstance(payload, dict):
                continue
            question_id = int(payload.get("question_id", 0))
            if question_id <= 0:
                continue
            max_id = max(max_id, question_id)
            entries.append(
                InboxEntry(
                    entry_id=question_id,
                    kind="system_question",
                    content=str(payload.get("content", "")),
                    created_at=float(payload.get("created_at", 0)),
                    channel=str(payload.get("channel", DEFAULT_CHANNEL)),
                    session_id=str(payload.get("session_id", DEFAULT_SESSION_ID)),
                    asked_by=payload.get("asked_by"),
                    status="answered",
                    answer=str(payload.get("answer", "")),
                    answered_at=float(payload.get("answered_at", 0)),
                )
            )
    if entries:
        global _next_entry_id
        with _pending_lock:
            _next_entry_id = max(max_id + 1, _next_entry_id)
    return entries
