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

    class DummyEnforcer:
        def clear_policy(self) -> None:
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
    monkeypatch.setattr(headless, "get_enforcer", lambda: DummyEnforcer())
    monkeypatch.setattr(headless, "configure_autogen_logging", lambda _dir: None)
    monkeypatch.setattr(headless, "get_runtime", lambda: DummyRuntime())
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

    class DummyEnforcer:
        def clear_policy(self) -> None:
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
    monkeypatch.setattr(headless, "get_enforcer", lambda: DummyEnforcer())
    monkeypatch.setattr(headless, "configure_autogen_logging", lambda _dir: None)
    monkeypatch.setattr(headless, "get_runtime", lambda: DummyRuntime())
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
