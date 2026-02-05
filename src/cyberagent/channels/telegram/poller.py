from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.error
from typing import Protocol

from autogen_core import AgentId, CancellationToken

from src.agents.messages import UserMessage
from src.cyberagent.channels.inbox import add_inbox_entry
from src.cyberagent.stt.postprocess import format_timestamped_text
from src.cyberagent.channels.telegram.client import TelegramClient
from src.cyberagent.channels.telegram import pairing as pairing_store
from src.cyberagent.channels.telegram import session_store
from src.cyberagent.channels.telegram import stt as telegram_stt
from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
)
from src.cyberagent.channels.telegram.parser import (
    build_reset_session_id,
    build_session_id,
    classify_text_message,
    extract_callback_queries,
    extract_text_messages,
    extract_voice_messages,
    is_allowed,
    parse_allowlist,
    parse_blocklist,
    TelegramCallbackQuery,
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
        self._allowed_chat_ids = parse_allowlist(
            os.environ.get("TELEGRAM_ALLOWLIST_CHAT_IDS")
            or os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS")
        )
        self._allowed_user_ids = parse_allowlist(
            os.environ.get("TELEGRAM_ALLOWLIST_USER_IDS")
            or os.environ.get("TELEGRAM_ALLOWED_USER_IDS")
        )
        self._blocked_chat_ids = parse_blocklist(
            os.environ.get("TELEGRAM_BLOCKLIST_CHAT_IDS")
            or os.environ.get("TELEGRAM_BLOCKED_CHAT_IDS")
        )
        self._blocked_user_ids = parse_blocklist(
            os.environ.get("TELEGRAM_BLOCKLIST_USER_IDS")
            or os.environ.get("TELEGRAM_BLOCKED_USER_IDS")
        )

    async def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                updates = await asyncio.to_thread(
                    self._client.get_updates, self._offset, self._timeout
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 409:
                    logger.error(
                        "Telegram polling stopped because a webhook is active. "
                        "Disable the webhook or set TELEGRAM_WEBHOOK_URL to use webhook mode."
                    )
                    return
                logger.exception("Telegram polling failed.")
                await asyncio.sleep(self._poll_interval)
                continue
            except Exception:  # pragma: no cover - network safety net
                logger.exception("Telegram polling failed.")
                await asyncio.sleep(self._poll_interval)
                continue
            messages = extract_text_messages(updates)
            for inbound in messages:
                if not is_allowed(
                    inbound.chat_id,
                    inbound.user_id,
                    self._allowed_chat_ids,
                    self._allowed_user_ids,
                    self._blocked_chat_ids,
                    self._blocked_user_ids,
                ):
                    logger.warning(
                        "Telegram message blocked (chat_id=%s user_id=%s).",
                        inbound.chat_id,
                        inbound.user_id,
                    )
                    await self._send_reply(inbound.chat_id, "Not authorized.")
                    self._offset = inbound.update_id + 1
                    continue
                logger.info(
                    "Telegram message received (chat_id=%s user_id=%s).",
                    inbound.chat_id,
                    inbound.user_id,
                )
                session_store.upsert_session(
                    chat_id=inbound.chat_id,
                    user_id=inbound.user_id,
                    chat_type=inbound.chat_type,
                    user_info={
                        "username": inbound.username,
                        "first_name": inbound.first_name,
                        "last_name": inbound.last_name,
                    },
                )
                if await self._handle_pairing_guard(
                    chat_id=inbound.chat_id,
                    user_id=inbound.user_id,
                    username=inbound.username,
                    first_name=inbound.first_name,
                    last_name=inbound.last_name,
                ):
                    self._offset = inbound.update_id + 1
                    continue
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
                if not is_allowed(
                    voice.chat_id,
                    voice.user_id,
                    self._allowed_chat_ids,
                    self._allowed_user_ids,
                    self._blocked_chat_ids,
                    self._blocked_user_ids,
                ):
                    logger.warning(
                        "Telegram voice blocked (chat_id=%s user_id=%s).",
                        voice.chat_id,
                        voice.user_id,
                    )
                    await asyncio.to_thread(
                        send_telegram_message, voice.chat_id, "Not authorized."
                    )
                    self._offset = voice.update_id + 1
                    continue
                logger.info(
                    "Telegram voice received (chat_id=%s user_id=%s).",
                    voice.chat_id,
                    voice.user_id,
                )
                session_store.upsert_session(
                    chat_id=voice.chat_id,
                    user_id=voice.user_id,
                    chat_type=voice.chat_type,
                    user_info={
                        "username": voice.username,
                        "first_name": voice.first_name,
                        "last_name": voice.last_name,
                    },
                )
                if await self._handle_pairing_guard(
                    chat_id=voice.chat_id,
                    user_id=voice.user_id,
                    username=voice.username,
                    first_name=voice.first_name,
                    last_name=voice.last_name,
                ):
                    self._offset = voice.update_id + 1
                    continue
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
                except Exception as exc:
                    logger.exception("Failed to transcribe Telegram voice message.")
                    await asyncio.to_thread(
                        send_telegram_message,
                        voice.chat_id,
                        telegram_stt.describe_transcription_error(exc),
                    )
                    self._offset = voice.update_id + 1
                    continue
                if self._stt_config.show_transcription:
                    await asyncio.to_thread(
                        send_telegram_message,
                        voice.chat_id,
                        f"Transcription: {result.text}",
                    )
                if result.low_confidence:
                    await asyncio.to_thread(
                        send_telegram_message,
                        voice.chat_id,
                        "Warning: audio quality appears low; transcript may be inaccurate.",
                    )
                inbox_text = format_timestamped_text(result.text, result.segments)
                add_inbox_entry(
                    "user_prompt",
                    inbox_text,
                    channel="telegram",
                    session_id=session_id,
                    metadata={
                        "telegram_chat_id": str(voice.chat_id),
                        "telegram_message_id": str(voice.message_id),
                        "telegram_file_id": voice.file_id,
                        "stt_provider": result.provider,
                        "stt_model": result.model,
                    },
                )
                message = UserMessage(content=result.text, source="User")
                message.metadata = {
                    "channel": "telegram",
                    "session_id": session_id,
                    "telegram_chat_id": str(voice.chat_id),
                    "telegram_message_id": str(voice.message_id),
                    "telegram_file_id": voice.file_id,
                    "inbox_recorded": "true",
                }
                await self._runtime.send_message(
                    message=message,
                    recipient=self._recipient,
                )
                self._offset = voice.update_id + 1
            callbacks = extract_callback_queries(updates)
            for callback in callbacks:
                if not is_allowed(
                    callback.chat_id,
                    callback.user_id,
                    self._allowed_chat_ids,
                    self._allowed_user_ids,
                    self._blocked_chat_ids,
                    self._blocked_user_ids,
                ):
                    logger.warning(
                        "Telegram callback blocked (chat_id=%s user_id=%s).",
                        callback.chat_id,
                        callback.user_id,
                    )
                    await asyncio.to_thread(
                        self._client.answer_callback_query,
                        callback.callback_id,
                        "Not authorized.",
                    )
                    self._offset = callback.update_id + 1
                    continue
                logger.info(
                    "Telegram callback received (chat_id=%s user_id=%s).",
                    callback.chat_id,
                    callback.user_id,
                )
                session_store.upsert_session(
                    chat_id=callback.chat_id,
                    user_id=callback.user_id,
                    chat_type=callback.chat_type,
                    user_info={
                        "username": callback.username,
                        "first_name": callback.first_name,
                        "last_name": callback.last_name,
                    },
                )
                if await self._handle_pairing_callback(callback):
                    self._offset = callback.update_id + 1
                    continue
                if await self._handle_pairing_guard(
                    chat_id=callback.chat_id,
                    user_id=callback.user_id,
                    username=callback.username,
                    first_name=callback.first_name,
                    last_name=callback.last_name,
                ):
                    await asyncio.to_thread(
                        self._client.answer_callback_query,
                        callback.callback_id,
                        "Not authorized.",
                    )
                    self._offset = callback.update_id + 1
                    continue
                await self._handle_callback(callback)
                self._offset = callback.update_id + 1
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
                "Commands: /start, /help, /reset, /ping",
            )
            return True
        if value == "/ping":
            # Support `/ping`, `/ping <payload>`, and `/ping@bot <payload>`.
            payload = text.strip().split(maxsplit=1)
            suffix = f" {payload[1]}" if len(payload) > 1 else ""
            await self._send_reply(inbound.chat_id, f"pong{suffix}")
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

    async def _handle_callback(self, callback: TelegramCallbackQuery) -> None:
        session_id = build_session_id(callback.chat_id, callback.user_id)
        message = UserMessage(content=callback.data, source="User")
        message.metadata = {
            "channel": "telegram",
            "session_id": session_id,
            "telegram_chat_id": str(callback.chat_id),
            "telegram_message_id": str(callback.message_id),
            "telegram_callback_id": callback.callback_id,
            "telegram_callback_data": callback.data,
        }
        await self._runtime.send_message(
            message=message,
            recipient=self._recipient,
        )
        await asyncio.to_thread(
            self._client.answer_callback_query, callback.callback_id, "Received."
        )

    async def _handle_pairing_callback(self, callback: TelegramCallbackQuery) -> bool:
        if not pairing_store.is_pairing_enabled():
            return False
        action = pairing_store.parse_pairing_callback(callback.data)
        if action is None:
            return False
        if action.action == pairing_store.PAIRING_CALLBACK_APPROVE:
            record = pairing_store.approve_pairing(
                action.code, admin_chat_id=callback.chat_id
            )
            response = "Pairing approved." if record else "Pairing code not found."
        else:
            record = pairing_store.deny_pairing(
                action.code, admin_chat_id=callback.chat_id
            )
            response = "Pairing denied." if record else "Pairing code not found."
        await asyncio.to_thread(
            self._client.answer_callback_query, callback.callback_id, response
        )
        if record and record.status == pairing_store.PAIRING_STATUS_APPROVED:
            await asyncio.to_thread(pairing_store.notify_user_approved, record)
        if record and record.status == pairing_store.PAIRING_STATUS_DENIED:
            await asyncio.to_thread(pairing_store.notify_user_denied, record)
        return True

    async def _handle_pairing_guard(
        self,
        *,
        chat_id: int,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> bool:
        if not pairing_store.is_pairing_enabled():
            return False
        admin_ids = pairing_store.load_admin_chat_ids()
        if admin_ids:
            if chat_id in admin_ids:
                return False
            await asyncio.to_thread(
                self._client.send_message,
                chat_id,
                "This bot is private and only the owner can chat.",
            )
            return True
        pairing_store.bootstrap_admin(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        await asyncio.to_thread(
            self._client.send_message,
            chat_id,
            "You're connected and set as the admin for this bot.",
        )
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
