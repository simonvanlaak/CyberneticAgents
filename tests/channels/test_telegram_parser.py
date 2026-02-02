from __future__ import annotations

from src.cyberagent.channels.telegram.parser import (
    TelegramInboundMessage,
    build_session_id,
    extract_text_messages,
)


def test_build_session_id_includes_chat_and_user() -> None:
    session_id = build_session_id(chat_id=123, user_id=456)
    assert session_id == "telegram:chat-123:user-456"


def test_extract_text_messages_filters_non_text() -> None:
    updates = [
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "from": {"id": 42},
                "chat": {"id": 99},
                "text": "hello",
            },
        },
        {
            "update_id": 2,
            "message": {
                "message_id": 11,
                "from": {"id": 42},
                "chat": {"id": 99},
            },
        },
        {"update_id": 3, "channel_post": {"message_id": 12}},
    ]

    messages = extract_text_messages(updates)

    assert messages == [
        TelegramInboundMessage(
            update_id=1,
            chat_id=99,
            user_id=42,
            text="hello",
        )
    ]
