from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramInboundMessage:
    update_id: int
    chat_id: int
    user_id: int
    text: str


def build_session_id(chat_id: int, user_id: int) -> str:
    return f"telegram:chat-{chat_id}:user-{user_id}"


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
