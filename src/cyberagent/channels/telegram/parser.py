from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True)
class TelegramInboundMessage:
    update_id: int
    chat_id: int
    user_id: int
    text: str


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
        messages.append(
            TelegramInboundMessage(
                update_id=update_id,
                chat_id=chat_id,
                user_id=user_id,
                text=text,
            )
        )
    return messages


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
            )
        )
    return messages
