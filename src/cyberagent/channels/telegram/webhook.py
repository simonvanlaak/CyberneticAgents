from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol

from autogen_core import AgentId, CancellationToken

from src.agents.messages import UserMessage
from src.cyberagent.channels.telegram.client import TelegramClient
from src.cyberagent.channels.telegram import stt as telegram_stt
from src.cyberagent.channels.telegram.parser import (
    TelegramInboundMessage,
    TelegramInboundVoiceMessage,
    build_reset_session_id,
    build_session_id,
    classify_text_message,
    extract_text_messages,
    extract_voice_messages,
    is_valid_secret,
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
                for message in inbound:
                    server._handle_inbound(message)
                for voice in voice_messages:
                    server._handle_voice_inbound(voice)
                self.send_response(200)
                self.end_headers()

        return TelegramWebhookHandler

    def _handle_inbound(self, inbound: TelegramInboundMessage) -> None:
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
                    "Commands: /start, /help, /reset",
                )
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
        except Exception:
            logger.exception("Failed to transcribe Telegram voice message.")
            self._client.send_message(
                inbound.chat_id, "Could not transcribe voice message."
            )
            return
        if self._stt_config.show_transcription:
            self._client.send_message(inbound.chat_id, f"Transcription: {result.text}")
        message = UserMessage(content=result.text, source="User")
        message.metadata = {
            "channel": "telegram",
            "session_id": session_id,
            "telegram_chat_id": str(inbound.chat_id),
            "telegram_message_id": str(inbound.message_id),
            "telegram_file_id": inbound.file_id,
        }
        future = asyncio.run_coroutine_threadsafe(
            self._runtime.send_message(message=message, recipient=self._recipient),
            self._loop,
        )
        future.add_done_callback(self._handle_forward_result)

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
