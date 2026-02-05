from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol

from autogen_core import AgentId, CancellationToken

from src.agents.messages import UserMessage
from src.cyberagent.channels.inbox import add_inbox_entry
from src.cyberagent.stt.postprocess import format_timestamped_text
from src.cyberagent.channels.telegram.client import TelegramClient
from src.cyberagent.channels.telegram import pairing as pairing_store
from src.cyberagent.channels.telegram import stt as telegram_stt
from src.cyberagent.channels.telegram import session_store
from src.cyberagent.channels.telegram.parser import (
    TelegramInboundMessage,
    TelegramInboundVoiceMessage,
    TelegramCallbackQuery,
    build_reset_session_id,
    build_session_id,
    classify_text_message,
    extract_callback_queries,
    extract_text_messages,
    extract_voice_messages,
    is_allowed,
    is_valid_secret,
    parse_allowlist,
    parse_blocklist,
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


class TelegramWebhookServer:
    def __init__(
        self,
        token: str,
        runtime: TelegramRuntime,
        recipient: AgentId,
        loop: asyncio.AbstractEventLoop,
        host: str,
        port: int,
        secret: str | None,
    ) -> None:
        self._client = TelegramClient(token)
        self._runtime = runtime
        self._recipient = recipient
        self._loop = loop
        self._host = host
        self._port = port
        self._secret = secret
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
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

    def start(self, webhook_url: str) -> None:
        handler = self._build_handler()
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="telegram-webhook",
            daemon=True,
        )
        self._thread.start()
        self._client.set_webhook(webhook_url, self._secret)
        logger.info(
            "Telegram webhook server listening on %s:%s", self._host, self._port
        )

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        try:
            self._client.delete_webhook()
        except Exception:  # pragma: no cover - safety net
            logger.exception("Failed to delete Telegram webhook.")

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class TelegramWebhookHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: N802
                return

            def do_POST(self) -> None:  # noqa: N802
                expected = server._secret
                headers = {k: v for k, v in self.headers.items()}
                if not is_valid_secret(headers, expected):
                    self.send_response(403)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.end_headers()
                    return
                updates = payload if isinstance(payload, list) else [payload]
                inbound = extract_text_messages(updates)
                voice_messages = extract_voice_messages(updates)
                callbacks = extract_callback_queries(updates)
                for message in inbound:
                    server._handle_inbound(message)
                for voice in voice_messages:
                    server._handle_voice_inbound(voice)
                for callback in callbacks:
                    server._handle_callback_inbound(callback)
                self.send_response(200)
                self.end_headers()

        return TelegramWebhookHandler

    def _handle_inbound(self, inbound: TelegramInboundMessage) -> None:
        if not is_allowed(
            inbound.chat_id,
            inbound.user_id,
            self._allowed_chat_ids,
            self._allowed_user_ids,
            self._blocked_chat_ids,
            self._blocked_user_ids,
        ):
            logger.warning(
                "Telegram webhook blocked (chat_id=%s user_id=%s).",
                inbound.chat_id,
                inbound.user_id,
            )
            self._client.send_message(inbound.chat_id, "Not authorized.")
            return
        logger.info(
            "Telegram webhook message received (chat_id=%s user_id=%s).",
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
        if self._handle_pairing_guard(
            chat_id=inbound.chat_id,
            user_id=inbound.user_id,
            username=inbound.username,
            first_name=inbound.first_name,
            last_name=inbound.last_name,
        ):
            return
        kind, value = classify_text_message(inbound.text)
        if kind == "command":
            if value == "/start":
                self._client.send_message(
                    inbound.chat_id,
                    "Telegram connected. Send a message to start a session.",
                )
                return
            if value == "/help":
                self._client.send_message(
                    inbound.chat_id,
                    "Commands: /start, /help, /reset, /ping",
                )
                return
            if value == "/ping":
                payload = inbound.text.strip().split(maxsplit=1)
                suffix = f" {payload[1]}" if len(payload) > 1 else ""
                self._client.send_message(inbound.chat_id, f"pong{suffix}")
                return
            if value == "/reset":
                reset_token = str(int(time.time()))
                session_id = build_reset_session_id(
                    inbound.chat_id, inbound.user_id, reset_token
                )
                self._forward_message(
                    "User requested to reset the session.",
                    session_id,
                    inbound.chat_id,
                    reset_session=True,
                )
                self._client.send_message(inbound.chat_id, "Session reset.")
                return
        session_id = build_session_id(inbound.chat_id, inbound.user_id)
        self._forward_message(inbound.text, session_id, inbound.chat_id)

    def _handle_voice_inbound(self, inbound: TelegramInboundVoiceMessage) -> None:
        if not is_allowed(
            inbound.chat_id,
            inbound.user_id,
            self._allowed_chat_ids,
            self._allowed_user_ids,
            self._blocked_chat_ids,
            self._blocked_user_ids,
        ):
            logger.warning(
                "Telegram webhook voice blocked (chat_id=%s user_id=%s).",
                inbound.chat_id,
                inbound.user_id,
            )
            self._client.send_message(inbound.chat_id, "Not authorized.")
            return
        logger.info(
            "Telegram webhook voice received (chat_id=%s user_id=%s).",
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
        if self._handle_pairing_guard(
            chat_id=inbound.chat_id,
            user_id=inbound.user_id,
            username=inbound.username,
            first_name=inbound.first_name,
            last_name=inbound.last_name,
        ):
            return
        session_id = build_session_id(inbound.chat_id, inbound.user_id)
        if (
            inbound.duration is not None
            and inbound.duration > self._stt_config.max_duration_seconds
        ):
            self._client.send_message(
                inbound.chat_id, "Voice message too long to transcribe."
            )
            return
        try:
            result = telegram_stt.transcribe_voice_message(
                self._client,
                inbound.file_id,
                self._stt_config,
                self._stt_cache_dir,
            )
        except Exception as exc:
            logger.exception("Failed to transcribe Telegram voice message.")
            self._client.send_message(
                inbound.chat_id, telegram_stt.describe_transcription_error(exc)
            )
            return
        if self._stt_config.show_transcription:
            self._client.send_message(inbound.chat_id, f"Transcription: {result.text}")
        if result.low_confidence:
            self._client.send_message(
                inbound.chat_id,
                "Warning: audio quality appears low; transcript may be inaccurate.",
            )
        inbox_text = format_timestamped_text(result.text, result.segments)
        add_inbox_entry(
            "user_prompt",
            inbox_text,
            channel="telegram",
            session_id=session_id,
            metadata={
                "telegram_chat_id": str(inbound.chat_id),
                "telegram_message_id": str(inbound.message_id),
                "telegram_file_id": inbound.file_id,
                "stt_provider": result.provider,
                "stt_model": result.model,
            },
        )
        message = UserMessage(content=result.text, source="User")
        message.metadata = {
            "channel": "telegram",
            "session_id": session_id,
            "telegram_chat_id": str(inbound.chat_id),
            "telegram_message_id": str(inbound.message_id),
            "telegram_file_id": inbound.file_id,
            "inbox_recorded": "true",
        }
        future = asyncio.run_coroutine_threadsafe(
            self._runtime.send_message(message=message, recipient=self._recipient),
            self._loop,
        )
        future.add_done_callback(self._handle_forward_result)

    def _handle_callback_inbound(self, callback: TelegramCallbackQuery) -> None:
        if not is_allowed(
            callback.chat_id,
            callback.user_id,
            self._allowed_chat_ids,
            self._allowed_user_ids,
            self._blocked_chat_ids,
            self._blocked_user_ids,
        ):
            logger.warning(
                "Telegram webhook callback blocked (chat_id=%s user_id=%s).",
                callback.chat_id,
                callback.user_id,
            )
            self._client.answer_callback_query(callback.callback_id, "Not authorized.")
            return
        logger.info(
            "Telegram webhook callback received (chat_id=%s user_id=%s).",
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
        if self._handle_pairing_callback(callback):
            return
        if self._handle_pairing_guard(
            chat_id=callback.chat_id,
            user_id=callback.user_id,
            username=callback.username,
            first_name=callback.first_name,
            last_name=callback.last_name,
        ):
            self._client.answer_callback_query(callback.callback_id, "Not authorized.")
            return
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
        future = asyncio.run_coroutine_threadsafe(
            self._runtime.send_message(message=message, recipient=self._recipient),
            self._loop,
        )
        future.add_done_callback(self._handle_forward_result)
        self._client.answer_callback_query(callback.callback_id, "Received.")

    def _handle_pairing_callback(self, callback: TelegramCallbackQuery) -> bool:
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
        self._client.answer_callback_query(callback.callback_id, response)
        if record and record.status == pairing_store.PAIRING_STATUS_APPROVED:
            pairing_store.notify_user_approved(record)
        if record and record.status == pairing_store.PAIRING_STATUS_DENIED:
            pairing_store.notify_user_denied(record)
        return True

    def _handle_pairing_guard(
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
            self._client.send_message(
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
        self._client.send_message(
            chat_id,
            "You're connected and set as the admin for this bot.",
        )
        return False

    def _forward_message(
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
        future = asyncio.run_coroutine_threadsafe(
            self._runtime.send_message(message=message, recipient=self._recipient),
            self._loop,
        )
        future.add_done_callback(self._handle_forward_result)

    @staticmethod
    def _handle_forward_result(future: Future[object]) -> None:
        try:
            future.result()
        except Exception:  # pragma: no cover - safety net
            logger.exception("Failed to forward Telegram webhook message.")
