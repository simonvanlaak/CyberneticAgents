import asyncio
from typing import cast

import pytest
from autogen_core import AgentId

from src.cyberagent.channels.telegram import pairing as pairing_module
from src.cyberagent.channels.telegram.parser import TelegramInboundMessage
from src.cyberagent.channels.telegram.webhook import TelegramWebhookServer
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.telegram_pairing import TelegramPairing


def _clear_pairings() -> None:
    session = next(get_db())
    try:
        session.query(TelegramPairing).delete()
        session.commit()
    finally:
        session.close()


def test_pairing_creates_pending_record() -> None:
    _clear_pairings()
    record, created = pairing_module.ensure_pairing(
        chat_id=10,
        user_id=20,
        username="alice",
        first_name="Alice",
        last_name="Example",
    )
    assert created is True
    assert record.status == pairing_module.PAIRING_STATUS_PENDING
    assert record.pairing_code
    record_again, created_again = pairing_module.ensure_pairing(
        chat_id=10,
        user_id=20,
        username="alice",
        first_name="Alice",
        last_name="Example",
    )
    assert created_again is False
    assert record_again.pairing_code == record.pairing_code


def test_pairing_approve_and_deny() -> None:
    _clear_pairings()
    record, _ = pairing_module.ensure_pairing(
        chat_id=11,
        user_id=22,
        username=None,
        first_name=None,
        last_name=None,
    )
    approved = pairing_module.approve_pairing(record.pairing_code, admin_chat_id=99)
    assert approved is not None
    assert approved.status == pairing_module.PAIRING_STATUS_APPROVED
    record2, _ = pairing_module.ensure_pairing(
        chat_id=33,
        user_id=44,
        username=None,
        first_name=None,
        last_name=None,
    )
    denied = pairing_module.deny_pairing(record2.pairing_code, admin_chat_id=99)
    assert denied is not None
    assert denied.status == pairing_module.PAIRING_STATUS_DENIED


def test_webhook_blocks_unpaired_and_sends_pairing_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_pairings()
    monkeypatch.delenv("TELEGRAM_PAIRING_ADMIN_CHAT_IDS", raising=False)

    class DummyClient:
        def __init__(self, token: str) -> None:
            self.messages: list[tuple[int, str]] = []

        def send_message(self, chat_id: int, text: str) -> None:
            self.messages.append((chat_id, text))

        def answer_callback_query(self, *args, **kwargs) -> None:  # noqa: ANN001
            return None

        def set_webhook(self, *args, **kwargs) -> None:  # noqa: ANN001
            return None

        def delete_webhook(self, *args, **kwargs) -> None:  # noqa: ANN001
            return None

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001,D401
            return None

    monkeypatch.setattr(
        "src.cyberagent.channels.telegram.webhook.TelegramClient", DummyClient
    )
    loop = asyncio.new_event_loop()
    server = TelegramWebhookServer(
        token="token",
        runtime=DummyRuntime(),
        recipient=AgentId(type="UserAgent", key="root"),
        loop=loop,
        host="127.0.0.1",
        port=0,
        secret=None,
    )
    forwarded: list[str] = []

    def _fake_forward(
        text: str, session_id: str, chat_id: int, reset_session: bool = False
    ) -> None:
        forwarded.append(text)

    monkeypatch.setattr(server, "_forward_message", _fake_forward)
    inbound = TelegramInboundMessage(
        update_id=1,
        chat_id=123,
        user_id=456,
        text="Hello",
        chat_type="private",
        username="alice",
        first_name="Alice",
        last_name="Example",
    )
    server._handle_inbound(inbound)
    assert forwarded == ["Hello"]
    client = cast(DummyClient, server._client)
    assert client.messages
    assert "admin" in client.messages[0][1].lower()
    loop.close()


def test_webhook_blocks_non_admin_when_admin_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_pairings()
    monkeypatch.setenv("TELEGRAM_PAIRING_ADMIN_CHAT_IDS", "999")

    class DummyClient:
        def __init__(self, token: str) -> None:
            self.messages: list[tuple[int, str]] = []

        def send_message(self, chat_id: int, text: str) -> None:
            self.messages.append((chat_id, text))

        def answer_callback_query(self, *args, **kwargs) -> None:  # noqa: ANN001
            return None

        def set_webhook(self, *args, **kwargs) -> None:  # noqa: ANN001
            return None

        def delete_webhook(self, *args, **kwargs) -> None:  # noqa: ANN001
            return None

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001,D401
            return None

    monkeypatch.setattr(
        "src.cyberagent.channels.telegram.webhook.TelegramClient", DummyClient
    )
    loop = asyncio.new_event_loop()
    server = TelegramWebhookServer(
        token="token",
        runtime=DummyRuntime(),
        recipient=AgentId(type="UserAgent", key="root"),
        loop=loop,
        host="127.0.0.1",
        port=0,
        secret=None,
    )
    forwarded: list[str] = []

    def _fake_forward(
        text: str, session_id: str, chat_id: int, reset_session: bool = False
    ) -> None:
        forwarded.append(text)

    monkeypatch.setattr(server, "_forward_message", _fake_forward)
    inbound = TelegramInboundMessage(
        update_id=1,
        chat_id=123,
        user_id=456,
        text="Hello",
        chat_type="private",
        username="alice",
        first_name="Alice",
        last_name="Example",
    )
    server._handle_inbound(inbound)
    assert forwarded == []
    client = cast(DummyClient, server._client)
    assert client.messages
    assert "private" in client.messages[0][1].lower()
    loop.close()
