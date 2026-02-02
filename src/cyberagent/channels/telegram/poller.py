from __future__ import annotations

import asyncio
import logging
import time
from typing import Protocol

from autogen_core import AgentId, CancellationToken

from src.agents.messages import UserMessage
from src.cyberagent.channels.telegram.client import TelegramClient
from src.cyberagent.channels.telegram import stt as telegram_stt
from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
)
from src.cyberagent.channels.telegram.parser import (
    build_reset_session_id,
    build_session_id,
    classify_text_message,
    extract_text_messages,
    extract_voice_messages,
    TelegramInboundMessage,
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
        self._stt_config = telegram_stt.load_config()
        self._stt_cache_dir = telegram_stt.get_cache_dir()

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
                if await self._handle_command(inbound):
                    self._offset = inbound.update_id + 1
                    continue
                session_id = build_session_id(inbound.chat_id, inbound.user_id)
                await self._forward_message(
                    inbound.text,
                    session_id,
                    inbound.chat_id,
                )
                self._offset = inbound.update_id + 1
            voice_messages = extract_voice_messages(updates)
            for voice in voice_messages:
                session_id = build_session_id(voice.chat_id, voice.user_id)
                if (
                    voice.duration is not None
                    and voice.duration > self._stt_config.max_duration_seconds
                ):
                    await asyncio.to_thread(
                        send_telegram_message,
                        voice.chat_id,
                        "Voice message too long to transcribe.",
                    )
                    self._offset = voice.update_id + 1
                    continue
                try:
                    result = await asyncio.to_thread(
                        telegram_stt.transcribe_voice_message,
                        self._client,
                        voice.file_id,
                        self._stt_config,
                        self._stt_cache_dir,
                    )
                except Exception:
                    logger.exception("Failed to transcribe Telegram voice message.")
                    await asyncio.to_thread(
                        send_telegram_message,
                        voice.chat_id,
                        "Could not transcribe voice message.",
                    )
                    self._offset = voice.update_id + 1
                    continue
                if self._stt_config.show_transcription:
                    await asyncio.to_thread(
                        send_telegram_message,
                        voice.chat_id,
                        f"Transcription: {result.text}",
                    )
                message = UserMessage(content=result.text, source="User")
                message.metadata = {
                    "channel": "telegram",
                    "session_id": session_id,
                    "telegram_chat_id": str(voice.chat_id),
                    "telegram_message_id": str(voice.message_id),
                    "telegram_file_id": voice.file_id,
                }
                await self._runtime.send_message(
                    message=message,
                    recipient=self._recipient,
                )
                self._offset = voice.update_id + 1
            await asyncio.sleep(self._poll_interval)

    async def _handle_command(self, inbound: TelegramInboundMessage) -> bool:
        text = inbound.text
        kind, value = classify_text_message(text)
        if kind != "command":
            return False
        if value == "/start":
            await self._send_reply(
                inbound.chat_id,
                "Telegram connected. Send a message to start a session.",
            )
            return True
        if value == "/help":
            await self._send_reply(
                inbound.chat_id,
                "Commands: /start, /help, /reset",
            )
            return True
        if value == "/reset":
            reset_token = str(int(time.time()))
            session_id = build_reset_session_id(
                inbound.chat_id, inbound.user_id, reset_token
            )
            await self._forward_message(
                "User requested to reset the session.",
                session_id,
                inbound.chat_id,
                reset_session=True,
            )
            await self._send_reply(inbound.chat_id, "Session reset.")
            return True
        return False

    async def _forward_message(
        self,
        text: str,
        session_id: str,
        chat_id: int,
        reset_session: bool = False,
    ) -> None:
        message = UserMessage(content=text, source="User")
        message.metadata = {
            "channel": "telegram",
            "session_id": session_id,
            "telegram_chat_id": str(chat_id),
            "reset_session": "true" if reset_session else "false",
        }
        await self._runtime.send_message(
            message=message,
            recipient=self._recipient,
        )

    async def _send_reply(self, chat_id: int, text: str) -> None:
        await asyncio.to_thread(self._client.send_message, chat_id, text)
