import asyncio
import urllib.error
from email.message import Message

import pytest

from src.cyberagent.channels.telegram import poller as poller_module


@pytest.mark.asyncio
async def test_telegram_poller_stops_on_webhook_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyClient:
        def __init__(self, token: str) -> None:
            self.token = token
            self.calls = 0

        def get_updates(
            self, offset: int | None, timeout: int
        ) -> list[dict[str, object]]:
            self.calls += 1
            raise urllib.error.HTTPError(
                url="https://api.telegram.org/bot123/getUpdates",
                code=409,
                msg="Conflict",
                hdrs=Message(),
                fp=None,
            )

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            return None

    monkeypatch.setattr(poller_module, "TelegramClient", DummyClient)

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(poller_module.asyncio, "to_thread", fake_to_thread)

    stop_event = asyncio.Event()
    poller = poller_module.TelegramPoller(
        token="token",
        runtime=DummyRuntime(),
        recipient=poller_module.AgentId(type="UserAgent", key="root"),
        stop_event=stop_event,
        poll_interval=0,
        timeout=1,
    )

    await asyncio.wait_for(poller.run(), timeout=1)
