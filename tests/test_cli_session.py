import asyncio
import time
from typing import cast

import pytest
from autogen_core import AgentId

from src.cli_session import (
    clear_pending_questions,
    enqueue_pending_question,
    forward_user_messages,
    get_answered_questions,
    get_pending_question,
    resolve_pending_question,
)
from src.agents.messages import UserMessage


class DummyRuntime:
    def __init__(self) -> None:
        self.sent_messages: list[UserMessage] = []
        self.sent_recipients: list[AgentId] = []

    async def send_message(self, message: UserMessage, recipient: AgentId) -> None:
        self.sent_messages.append(message)
        self.sent_recipients.append(recipient)


@pytest.mark.asyncio
async def test_forward_user_messages_sends_to_runtime() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = asyncio.Event()
    runtime = DummyRuntime()
    recipient = AgentId(type="UserAgent", key="root")

    task = asyncio.create_task(
        forward_user_messages(queue, runtime, recipient, stop_event)
    )

    await queue.put("hello")
    await asyncio.sleep(0.01)

    stop_event.set()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert len(runtime.sent_messages) == 1
    assert runtime.sent_messages[0].content == "hello"
    assert runtime.sent_recipients[0] == recipient


@pytest.mark.asyncio
async def test_forward_user_messages_exit_command_stops() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = asyncio.Event()
    runtime = DummyRuntime()
    recipient = AgentId(type="UserAgent", key="root")

    task = asyncio.create_task(
        forward_user_messages(queue, runtime, recipient, stop_event)
    )

    await queue.put("/exit")
    await asyncio.sleep(0.01)

    assert stop_event.is_set()
    assert runtime.sent_messages == []

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def test_pending_question_fifo_and_answer_archive() -> None:
    clear_pending_questions()
    assert get_pending_question() is None


def test_read_stdin_handles_pending_and_eof(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import src.cli_session as cli_session

    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = asyncio.Event()

    class DummyLoop:
        def call_soon_threadsafe(self, fn, *args) -> None:  # type: ignore[no-untyped-def]
            fn(*args)

    inputs = iter(["hello", "", "world"])

    def fake_input(_: str) -> str:
        try:
            return next(inputs)
        except StopIteration as exc:
            raise EOFError from exc

    pending = iter(
        [
            cli_session.PendingQuestion(
                content="Any updates?",
                asked_by="System4",
                question_id=1,
                created_at=time.time(),
            ),
            None,
            None,
        ]
    )

    monkeypatch.setattr(
        cli_session, "get_pending_question", lambda **_: next(pending, None)
    )
    monkeypatch.setattr("builtins.input", fake_input)

    cli_session._read_stdin(
        cast(asyncio.AbstractEventLoop, DummyLoop()), queue, stop_event
    )

    captured = capsys.readouterr()
    assert "Pending question (System4)" in captured.out
    assert stop_event.is_set()
    assert queue.get_nowait() == "hello"
    assert queue.get_nowait() == "world"

    enqueue_pending_question("Where should I focus next?", asked_by="System4")
    enqueue_pending_question("Any other constraints?", asked_by="System4")

    first = get_pending_question()
    assert first is not None
    assert first.content == "Where should I focus next?"

    resolved = resolve_pending_question("Focus on tool design.")
    assert resolved is not None
    assert resolved.content == "Where should I focus next?"
    assert resolved.answer == "Focus on tool design."

    next_pending = get_pending_question()
    assert next_pending is not None
    assert next_pending.content == "Any other constraints?"

    answered = get_answered_questions()
    assert len(answered) == 1
    assert answered[0].content == "Where should I focus next?"

    clear_pending_questions()
    assert get_pending_question() is None
