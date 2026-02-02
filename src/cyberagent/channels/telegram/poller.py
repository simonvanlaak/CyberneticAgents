from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from autogen_core import AgentId, CancellationToken

from src.agents.messages import UserMessage
from src.cyberagent.channels.telegram.client import TelegramClient
from src.cyberagent.channels.telegram.parser import (
    build_session_id,
    extract_text_messages,
)

logger = logging.getLogger(__name__)


class TelegramRuntime(Protocol):
    async def send_message(  # noqa: D401
        self,
        message: object,
        recipient: AgentId,
        *,
        sender: AgentId | None = None,
        cancellation_token: CancellationToken | None = None,
        message_id: str | None = None,
    ) -> object:
        """Send a message to the runtime."""


class TelegramPoller:
    def __init__(
        self,
        token: str,
        runtime: TelegramRuntime,
        recipient: AgentId,
        stop_event: asyncio.Event,
        poll_interval: float = 1.0,
        timeout: int = 20,
    ) -> None:
        self._client = TelegramClient(token)
        self._runtime = runtime
        self._recipient = recipient
        self._stop_event = stop_event
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._offset: int | None = None

    async def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                updates = await asyncio.to_thread(
                    self._client.get_updates, self._offset, self._timeout
                )
            except Exception:  # pragma: no cover - network safety net
                logger.exception("Telegram polling failed.")
                await asyncio.sleep(self._poll_interval)
                continue
            messages = extract_text_messages(updates)
            for inbound in messages:
                session_id = build_session_id(inbound.chat_id, inbound.user_id)
                message = UserMessage(content=inbound.text, source="User")
                message.metadata = {
                    "channel": "telegram",
                    "session_id": session_id,
                    "telegram_chat_id": str(inbound.chat_id),
                }
                await self._runtime.send_message(
                    message=message,
                    recipient=self._recipient,
                )
                self._offset = inbound.update_id + 1
            await asyncio.sleep(self._poll_interval)
