import asyncio
from typing import Protocol

from autogen_core import AgentId

from src.agents.messages import UserMessage
from src.cyberagent.channels.inbox import (
    InboxEntry,
    AnsweredQuestion,
    PendingQuestion,
    add_inbox_entry,
    clear_pending_questions,
    enqueue_pending_question,
    get_answered_questions,
    get_pending_question,
    get_pending_questions,
    list_inbox_entries,
    list_inbox_answered_questions,
    list_inbox_pending_questions,
    resolve_pending_question,
    wait_for_answer,
)
from src.cyberagent.channels.inbox import DEFAULT_CHANNEL, DEFAULT_SESSION_ID

__all__ = [
    "InboxEntry",
    "AnsweredQuestion",
    "PendingQuestion",
    "add_inbox_entry",
    "clear_pending_questions",
    "enqueue_pending_question",
    "get_answered_questions",
    "get_pending_question",
    "get_pending_questions",
    "list_inbox_entries",
    "list_inbox_answered_questions",
    "list_inbox_pending_questions",
    "resolve_pending_question",
    "wait_for_answer",
    "read_stdin_loop",
    "forward_user_messages",
]


class MessageRuntime(Protocol):
    async def send_message(self, message: UserMessage, recipient: AgentId) -> None: ...


def _read_stdin(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[str],
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        pending_question = get_pending_question(
            channel=DEFAULT_CHANNEL, session_id=DEFAULT_SESSION_ID
        )
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
        message.metadata = {
            "channel": DEFAULT_CHANNEL,
            "session_id": DEFAULT_SESSION_ID,
        }
        await runtime.send_message(message=message, recipient=recipient)
