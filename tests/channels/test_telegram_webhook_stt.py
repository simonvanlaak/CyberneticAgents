from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from autogen_core import AgentId

from src.cyberagent.channels.telegram import stt as telegram_stt
from src.cyberagent.channels.telegram import webhook
from src.cyberagent.channels.telegram.parser import TelegramInboundVoiceMessage
from src.cyberagent.channels.telegram.webhook import TelegramWebhookServer


class _Runtime:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def send_message(
        self, message: object, recipient: object, **kwargs: object
    ) -> object:
        self.messages.append(message)
        return {}


def test_webhook_transcribes_voice_message(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _Runtime()
    server = TelegramWebhookServer(
        token="token",
        runtime=runtime,
        recipient=AgentId.from_str("UserAgent/root"),
        loop=object(),  # type: ignore[arg-type]
        host="127.0.0.1",
        port=0,
        secret=None,
    )

    sent: list[str] = []

    def _fake_send_message(chat_id: int, text: str) -> None:
        sent.append(f"{chat_id}:{text}")

    monkeypatch.setattr(server._client, "send_message", _fake_send_message)
    monkeypatch.setattr(webhook, "add_inbox_entry", lambda *_args, **_kwargs: None)

    def _fake_transcribe(
        *args: object, **kwargs: object
    ) -> telegram_stt.TranscriptionResult:
        return telegram_stt.TranscriptionResult(
            text="hello world",
            provider="groq",
            model="whisper-large-v3-turbo",
            language="en",
            segments=[],
        )

    monkeypatch.setattr(telegram_stt, "transcribe_voice_message", _fake_transcribe)

    class _ImmediateFuture:
        def __init__(self, value: object) -> None:
            self._value = value

        def add_done_callback(self, callback: Callable[[object], object]) -> None:
            callback(self)

        def result(self) -> object:
            return self._value

    def _run_sync(coro: Coroutine[Any, Any, object], _loop: object) -> _ImmediateFuture:
        return _ImmediateFuture(asyncio.run(coro))

    monkeypatch.setattr(webhook.asyncio, "run_coroutine_threadsafe", _run_sync)

    inbound = TelegramInboundVoiceMessage(
        update_id=1,
        chat_id=123,
        user_id=456,
        message_id=99,
        file_id="file-1",
        file_unique_id="uniq",
        duration=5,
        mime_type="audio/ogg",
        file_name=None,
    )

    server._handle_voice_inbound(inbound)

    assert sent == ["123:Transcription: hello world"]
    assert len(runtime.messages) == 1


def test_webhook_adds_inbox_entry_for_voice_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _Runtime()
    server = TelegramWebhookServer(
        token="token",
        runtime=runtime,
        recipient=AgentId.from_str("UserAgent/root"),
        loop=object(),  # type: ignore[arg-type]
        host="127.0.0.1",
        port=0,
        secret=None,
    )

    monkeypatch.setattr(server._client, "send_message", lambda *_args, **_kwargs: None)

    def _fake_transcribe(
        *args: object, **kwargs: object
    ) -> telegram_stt.TranscriptionResult:
        return telegram_stt.TranscriptionResult(
            text="hello inbox",
            provider="openai",
            model="whisper-1",
            language="en",
            segments=[],
        )

    monkeypatch.setattr(telegram_stt, "transcribe_voice_message", _fake_transcribe)

    class _ImmediateFuture:
        def __init__(self, value: object) -> None:
            self._value = value

        def add_done_callback(self, callback: Callable[[object], object]) -> None:
            callback(self)

        def result(self) -> object:
            return self._value

    def _run_sync(coro: Coroutine[Any, Any, object], _loop: object) -> _ImmediateFuture:
        return _ImmediateFuture(asyncio.run(coro))

    monkeypatch.setattr(webhook.asyncio, "run_coroutine_threadsafe", _run_sync)

    recorded: dict[str, object] = {}

    def _fake_add_inbox_entry(*args: object, **kwargs: object) -> None:
        if args:
            recorded["kind"] = args[0]
        if len(args) > 1:
            recorded["content"] = args[1]
        recorded.update(kwargs)

    monkeypatch.setattr(webhook, "add_inbox_entry", _fake_add_inbox_entry)

    inbound = TelegramInboundVoiceMessage(
        update_id=1,
        chat_id=123,
        user_id=456,
        message_id=99,
        file_id="file-1",
        file_unique_id="uniq",
        duration=5,
        mime_type="audio/ogg",
        file_name=None,
    )

    server._handle_voice_inbound(inbound)

    assert recorded["kind"] == "user_prompt"
    assert recorded["content"] == "hello inbox"
    assert recorded["channel"] == "telegram"
    assert recorded["session_id"] == "telegram:chat-123:user-456"
    metadata = recorded["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["telegram_chat_id"] == "123"
    assert metadata["telegram_message_id"] == "99"
    assert metadata["telegram_file_id"] == "file-1"
    assert "original_audio" not in metadata


def test_webhook_injects_timestamps_for_long_transcripts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _Runtime()
    server = TelegramWebhookServer(
        token="token",
        runtime=runtime,
        recipient=AgentId.from_str("UserAgent/root"),
        loop=object(),  # type: ignore[arg-type]
        host="127.0.0.1",
        port=0,
        secret=None,
    )

    monkeypatch.setattr(server._client, "send_message", lambda *_args, **_kwargs: None)

    long_text = "word " * 60

    def _fake_transcribe(
        *args: object, **kwargs: object
    ) -> telegram_stt.TranscriptionResult:
        return telegram_stt.TranscriptionResult(
            text=long_text,
            provider="openai",
            model="whisper-1",
            language="en",
            segments=[
                {"start": 0.0, "text": "Hello"},
                {"start": 65.4, "text": "World"},
            ],
        )

    monkeypatch.setattr(telegram_stt, "transcribe_voice_message", _fake_transcribe)

    class _ImmediateFuture:
        def __init__(self, value: object) -> None:
            self._value = value

        def add_done_callback(self, callback: Callable[[object], object]) -> None:
            callback(self)

        def result(self) -> object:
            return self._value

    def _run_sync(coro: Coroutine[Any, Any, object], _loop: object) -> _ImmediateFuture:
        return _ImmediateFuture(asyncio.run(coro))

    monkeypatch.setattr(webhook.asyncio, "run_coroutine_threadsafe", _run_sync)

    recorded: dict[str, object] = {}

    def _fake_add_inbox_entry(*args: object, **kwargs: object) -> None:
        if args:
            recorded["content"] = args[1]
        recorded.update(kwargs)

    monkeypatch.setattr(webhook, "add_inbox_entry", _fake_add_inbox_entry)

    inbound = TelegramInboundVoiceMessage(
        update_id=1,
        chat_id=123,
        user_id=456,
        message_id=99,
        file_id="file-1",
        file_unique_id="uniq",
        duration=5,
        mime_type="audio/ogg",
        file_name=None,
    )

    server._handle_voice_inbound(inbound)

    assert "[00:00] Hello" in str(recorded["content"])
    assert "[01:05] World" in str(recorded["content"])
