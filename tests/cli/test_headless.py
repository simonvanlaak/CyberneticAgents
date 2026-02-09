import asyncio
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from src.cyberagent.cli import headless
from src.cyberagent.cli import agent_message_queue


@pytest.mark.asyncio
async def test_run_headless_session_starts_cli_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, bool] = {"value": False}
    stopped: dict[str, bool] = {"value": False}

    async def fake_start_cli_executor() -> None:
        started["value"] = True

    async def fake_stop_runtime() -> None:
        stopped["value"] = True

    async def fake_register() -> None:
        return None

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            return None

    async def fake_read_stdin(queue, stop_event):  # noqa: ANN001
        stop_event.set()

    async def fake_forward(queue, runtime, recipient, stop_event):  # noqa: ANN001
        return None

    monkeypatch.setattr(headless, "init_db", lambda: None)
    monkeypatch.setattr(headless, "register_systems", fake_register)
    monkeypatch.setattr(headless, "configure_autogen_logging", lambda _dir: None)
    monkeypatch.setattr(headless, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(headless, "_stdin_is_interactive", lambda: True)
    monkeypatch.setattr(headless, "read_stdin_loop", fake_read_stdin)
    monkeypatch.setattr(headless, "forward_user_messages", fake_forward)
    monkeypatch.setattr(headless, "start_cli_executor", fake_start_cli_executor)
    monkeypatch.setattr(headless, "stop_runtime", fake_stop_runtime)

    await headless.run_headless_session()

    assert started["value"] is True
    assert stopped["value"] is True


@pytest.mark.asyncio
async def test_run_headless_session_starts_webhook_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, bool] = {"value": False}
    stopped: dict[str, bool] = {"value": False}
    poller_used: dict[str, bool] = {"value": False}

    async def fake_start_cli_executor() -> None:
        return None

    async def fake_stop_runtime() -> None:
        return None

    async def fake_register() -> None:
        return None

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            return None

    async def fake_read_stdin(queue, stop_event):  # noqa: ANN001
        stop_event.set()

    async def fake_forward(queue, runtime, recipient, stop_event):  # noqa: ANN001
        return None

    class DummyWebhook:
        def __init__(self, *args, **kwargs):  # noqa: ANN001
            return None

        def start(self, webhook_url: str) -> None:
            assert webhook_url == "https://example.com/telegram"
            started["value"] = True

        def stop(self) -> None:
            stopped["value"] = True

    class DummyPoller:
        def __init__(self, *args, **kwargs):  # noqa: ANN001
            poller_used["value"] = True

        async def run(self) -> None:
            return None

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://example.com/telegram")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_HOST", "127.0.0.1")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_PORT", "8080")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")

    monkeypatch.setattr(headless, "init_db", lambda: None)
    monkeypatch.setattr(headless, "register_systems", fake_register)
    monkeypatch.setattr(headless, "configure_autogen_logging", lambda _dir: None)
    monkeypatch.setattr(headless, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(headless, "_stdin_is_interactive", lambda: True)
    monkeypatch.setattr(headless, "read_stdin_loop", fake_read_stdin)
    monkeypatch.setattr(headless, "forward_user_messages", fake_forward)
    monkeypatch.setattr(headless, "start_cli_executor", fake_start_cli_executor)
    monkeypatch.setattr(headless, "stop_runtime", fake_stop_runtime)
    monkeypatch.setattr(headless, "TelegramWebhookServer", DummyWebhook)
    monkeypatch.setattr(headless, "TelegramPoller", DummyPoller)

    await headless.run_headless_session()

    assert started["value"] is True
    assert stopped["value"] is True
    assert poller_used["value"] is False


@pytest.mark.asyncio
async def test_run_headless_session_skips_reader_without_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader_called: dict[str, bool] = {"value": False}
    stopped: dict[str, bool] = {"value": False}

    async def fake_register() -> None:
        return None

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            return None

    async def fake_read_stdin(queue, stop_event):  # noqa: ANN001
        reader_called["value"] = True
        stop_event.set()

    async def fake_start_cli_executor() -> None:
        return None

    async def fake_forward(queue, runtime, recipient, stop_event):  # noqa: ANN001
        await stop_event.wait()

    async def fake_process_suggestion_queue(runtime, stop_event):  # noqa: ANN001
        stop_event.set()

    async def fake_process_agent_message_queue(runtime, stop_event):  # noqa: ANN001
        await stop_event.wait()

    async def fake_stop_runtime() -> None:
        stopped["value"] = True

    monkeypatch.setattr(headless, "init_db", lambda: None)
    monkeypatch.setattr(headless, "register_systems", fake_register)
    monkeypatch.setattr(headless, "configure_autogen_logging", lambda _dir: None)
    monkeypatch.setattr(headless, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(headless, "_stdin_is_interactive", lambda: False)
    monkeypatch.setattr(headless, "read_stdin_loop", fake_read_stdin)
    monkeypatch.setattr(headless, "forward_user_messages", fake_forward)
    monkeypatch.setattr(headless, "start_cli_executor", fake_start_cli_executor)
    monkeypatch.setattr(
        headless, "_process_suggestion_queue", fake_process_suggestion_queue
    )
    monkeypatch.setattr(
        headless, "_process_agent_message_queue", fake_process_agent_message_queue
    )
    monkeypatch.setattr(headless, "stop_runtime", fake_stop_runtime)

    await headless.run_headless_session()

    assert reader_called["value"] is False
    assert stopped["value"] is True


@pytest.mark.asyncio
async def test_agent_message_queue_stops_on_disk_io_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent_message_queue.AGENT_MESSAGE_QUEUE_DIR = tmp_path
    agent_message_queue.enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "Onboarding", "content": "Start."},
    )

    class FailingRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            raise OperationalError(
                "statement",
                {},
                sqlite3.OperationalError("disk I/O error"),
            )

    monkeypatch.setattr(headless, "SUGGEST_QUEUE_POLL_SECONDS", 0)
    stop_event = asyncio.Event()

    await asyncio.wait_for(
        headless._process_agent_message_queue(FailingRuntime(), stop_event),
        timeout=1,
    )

    assert stop_event.is_set() is True
    assert list(tmp_path.glob("*.json"))


@pytest.mark.asyncio
async def test_agent_message_queue_defers_on_non_disk_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queued_path = tmp_path / "queued.json"
    queued_path.write_text("{}", encoding="utf-8")
    queued_message = agent_message_queue.QueuedAgentMessage(
        path=queued_path,
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
        idempotency_key="agent_message:test",
        queued_at=0.0,
        attempts=0,
        next_attempt_at=0.0,
    )
    calls: dict[str, int] = {"defer": 0}
    stop_event = asyncio.Event()

    class FailingRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            raise RuntimeError("connection error")

    monkeypatch.setattr(
        headless, "read_queued_agent_messages", lambda: [queued_message]
    )
    monkeypatch.setattr(headless, "SUGGEST_QUEUE_POLL_SECONDS", 0)

    def _defer(**kwargs: object) -> bool:
        calls["defer"] += 1
        stop_event.set()
        return False

    monkeypatch.setattr(headless, "defer_agent_message", _defer)

    await asyncio.wait_for(
        headless._process_agent_message_queue(FailingRuntime(), stop_event),
        timeout=1,
    )

    assert calls["defer"] == 1


@pytest.mark.asyncio
async def test_agent_message_queue_skips_already_processed_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queued_path = tmp_path / "queued.json"
    queued_path.write_text("{}", encoding="utf-8")
    queued_message = agent_message_queue.QueuedAgentMessage(
        path=queued_path,
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
        idempotency_key="agent_message:already-processed",
        queued_at=0.0,
        attempts=0,
        next_attempt_at=0.0,
    )
    stop_event = asyncio.Event()
    calls: dict[str, int] = {"acked": 0}

    class RuntimeSpy:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            raise AssertionError("send_message should not be called for replay")

    monkeypatch.setattr(
        headless, "read_queued_agent_messages", lambda: [queued_message]
    )
    monkeypatch.setattr(headless, "SUGGEST_QUEUE_POLL_SECONDS", 0)
    monkeypatch.setattr(headless, "was_processed_message", lambda *_: True)

    def _ack(_path: Path) -> None:
        calls["acked"] += 1
        stop_event.set()

    monkeypatch.setattr(headless, "ack_agent_message", _ack)

    await asyncio.wait_for(
        headless._process_agent_message_queue(RuntimeSpy(), stop_event),
        timeout=1,
    )

    assert calls["acked"] == 1


@pytest.mark.asyncio
async def test_agent_message_queue_marks_processed_before_ack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queued_path = tmp_path / "queued.json"
    queued_path.write_text("{}", encoding="utf-8")
    queued_message = agent_message_queue.QueuedAgentMessage(
        path=queued_path,
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={"initiative_id": 1, "source": "System4_root", "content": "Resume."},
        idempotency_key="agent_message:new",
        queued_at=0.0,
        attempts=0,
        next_attempt_at=0.0,
    )
    stop_event = asyncio.Event()
    order: list[str] = []

    class RuntimeOk:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            order.append("send")
            return None

    monkeypatch.setattr(
        headless, "read_queued_agent_messages", lambda: [queued_message]
    )
    monkeypatch.setattr(headless, "SUGGEST_QUEUE_POLL_SECONDS", 0)
    monkeypatch.setattr(headless, "was_processed_message", lambda *_: False)

    def _mark(_scope: str, _key: str) -> None:
        order.append("mark")

    def _ack(_path: Path) -> None:
        order.append("ack")
        stop_event.set()

    monkeypatch.setattr(headless, "mark_processed_message", _mark)
    monkeypatch.setattr(headless, "ack_agent_message", _ack)

    await asyncio.wait_for(
        headless._process_agent_message_queue(RuntimeOk(), stop_event),
        timeout=1,
    )

    assert order == ["send", "mark", "ack"]


def test_build_agent_message_normalizes_invalid_source_name() -> None:
    message = headless._build_agent_message(
        "initiative_assign",
        {
            "initiative_id": 5,
            "source": "System4/root",
            "content": "Resume initiative 5.",
        },
    )

    assert isinstance(message, headless.InitiativeAssignMessage)
    assert message.source == "System4_root"


def test_build_task_review_message_normalizes_invalid_source_name() -> None:
    message = headless._build_agent_message(
        "task_review",
        {
            "task_id": 42,
            "assignee_agent_id_str": "System1/root",
            "source": "System1/root",
            "content": "Done.",
        },
    )

    assert isinstance(message, headless.TaskReviewMessage)
    assert message.task_id == 42
    assert message.assignee_agent_id_str == "System1/root"
    assert message.source == "System1_root"
