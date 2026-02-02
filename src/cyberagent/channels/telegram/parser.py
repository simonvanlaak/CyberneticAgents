from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True)
class TelegramInboundMessage:
    update_id: int
    chat_id: int
    user_id: int
    text: str
    chat_type: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True)
class TelegramInboundVoiceMessage:
    update_id: int
    chat_id: int
    user_id: int
    message_id: int
    file_id: str
    file_unique_id: str | None
    duration: int | None
    mime_type: str | None
    file_name: str | None
    chat_type: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True)
class TelegramCallbackQuery:
    update_id: int
    callback_id: str
    chat_id: int
    user_id: int
    message_id: int
    data: str
    chat_type: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


def build_session_id(chat_id: int, user_id: int) -> str:
    return f"telegram:chat-{chat_id}:user-{user_id}"


def build_reset_session_id(chat_id: int, user_id: int, reset_token: str) -> str:
    return f"telegram:chat-{chat_id}:user-{user_id}:reset-{reset_token}"


def classify_text_message(text: str) -> Tuple[str, str]:
    normalized = text.strip()
    if normalized.startswith("/"):
        command = normalized.split(maxsplit=1)[0].lower()
        if command in {"/start", "/help", "/reset"}:
            return ("command", command)
    return ("text", text)


def is_valid_secret(headers: Mapping[str, str], expected: str | None) -> bool:
    if not expected:
        return True
    lowered = {key.lower(): value for key, value in headers.items()}
    return lowered.get("x-telegram-bot-api-secret-token") == expected


def parse_allowlist(value: str | None) -> set[int]:
    return _parse_id_set(value)


def parse_blocklist(value: str | None) -> set[int]:
    return _parse_id_set(value)


def _parse_id_set(value: str | None) -> set[int]:
    if not value:
        return set()
    entries = [item.strip() for item in value.split(",")]
    return {int(item) for item in entries if item.isdigit()}


def is_allowed(
    chat_id: int,
    user_id: int,
    allowed_chats: set[int],
    allowed_users: set[int],
    blocked_chats: set[int] | None = None,
    blocked_users: set[int] | None = None,
) -> bool:
    blocked_chats = blocked_chats or set()
    blocked_users = blocked_users or set()
    if chat_id in blocked_chats or user_id in blocked_users:
        return False
    if not allowed_chats and not allowed_users:
        return True
    return chat_id in allowed_chats or user_id in allowed_users


def extract_text_messages(
    updates: list[dict[str, object]],
) -> list[TelegramInboundMessage]:
    messages: list[TelegramInboundMessage] = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        update_id = update.get("update_id")
        message = update.get("message")
        if not isinstance(update_id, int):
            continue
        if not isinstance(message, dict):
            continue
        text = message.get("text")
        if not isinstance(text, str) or not text:
            continue
        chat = message.get("chat")
        sender = message.get("from")
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            continue
        chat_id = chat.get("id")
        user_id = sender.get("id")
        if not isinstance(chat_id, int) or not isinstance(user_id, int):
            continue
        chat_type = chat.get("type")
        if not isinstance(chat_type, str):
            chat_type = None
        username = sender.get("username")
        if not isinstance(username, str):
            username = None
        first_name = sender.get("first_name")
        if not isinstance(first_name, str):
            first_name = None
        last_name = sender.get("last_name")
        if not isinstance(last_name, str):
            last_name = None
        messages.append(
            TelegramInboundMessage(
                update_id=update_id,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                chat_type=chat_type,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
        )
    return messages


def extract_callback_queries(
    updates: list[dict[str, object]],
) -> list[TelegramCallbackQuery]:
    callbacks: list[TelegramCallbackQuery] = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        update_id = update.get("update_id")
        payload = update.get("callback_query")
        if not isinstance(update_id, int):
            continue
        if not isinstance(payload, dict):
            continue
        callback_id = payload.get("id")
        data = payload.get("data")
        sender = payload.get("from")
        message = payload.get("message")
        if not isinstance(callback_id, str) or not callback_id:
            continue
        if not isinstance(data, str) or not data:
            continue
        if not isinstance(sender, dict) or not isinstance(message, dict):
            continue
        user_id = sender.get("id")
        message_id = message.get("message_id")
        chat = message.get("chat")
        if not isinstance(user_id, int) or not isinstance(message_id, int):
            continue
        if not isinstance(chat, dict):
            continue
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            continue
        chat_type = chat.get("type")
        if not isinstance(chat_type, str):
            chat_type = None
        username = sender.get("username")
        if not isinstance(username, str):
            username = None
        first_name = sender.get("first_name")
        if not isinstance(first_name, str):
            first_name = None
        last_name = sender.get("last_name")
        if not isinstance(last_name, str):
            last_name = None
        callbacks.append(
            TelegramCallbackQuery(
                update_id=update_id,
                callback_id=callback_id,
                chat_id=chat_id,
                user_id=user_id,
                message_id=message_id,
                data=data,
                chat_type=chat_type,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
        )
    return callbacks


def extract_voice_messages(
    updates: list[dict[str, object]],
) -> list[TelegramInboundVoiceMessage]:
    messages: list[TelegramInboundVoiceMessage] = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        update_id = update.get("update_id")
        message = update.get("message")
        if not isinstance(update_id, int):
            continue
        if not isinstance(message, dict):
            continue
        chat = message.get("chat")
        sender = message.get("from")
        message_id = message.get("message_id")
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            continue
        if not isinstance(message_id, int):
            continue
        chat_id = chat.get("id")
        user_id = sender.get("id")
        if not isinstance(chat_id, int) or not isinstance(user_id, int):
            continue
        chat_type = chat.get("type")
        if not isinstance(chat_type, str):
            chat_type = None
        username = sender.get("username")
        if not isinstance(username, str):
            username = None
        first_name = sender.get("first_name")
        if not isinstance(first_name, str):
            first_name = None
        last_name = sender.get("last_name")
        if not isinstance(last_name, str):
            last_name = None
        voice = message.get("voice")
        audio = message.get("audio")
        payload = (
            voice
            if isinstance(voice, dict)
            else audio if isinstance(audio, dict) else None
        )
        if payload is None:
            continue
        file_id = payload.get("file_id")
        if not isinstance(file_id, str) or not file_id:
            continue
        file_unique_id = payload.get("file_unique_id")
        if not isinstance(file_unique_id, str):
            file_unique_id = None
        duration = payload.get("duration")
        if not isinstance(duration, int):
            duration = None
        mime_type = payload.get("mime_type")
        if not isinstance(mime_type, str):
            mime_type = None
        file_name = payload.get("file_name")
        if not isinstance(file_name, str):
            file_name = None
        messages.append(
            TelegramInboundVoiceMessage(
                update_id=update_id,
                chat_id=chat_id,
                user_id=user_id,
                message_id=message_id,
                file_id=file_id,
                file_unique_id=file_unique_id,
                duration=duration,
                mime_type=mime_type,
                file_name=file_name,
                chat_type=chat_type,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
        )
    return messages
