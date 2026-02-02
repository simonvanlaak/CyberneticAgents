from __future__ import annotations

from src.cyberagent.channels.telegram.parser import (
    TelegramInboundMessage,
    build_reset_session_id,
    build_session_id,
    classify_text_message,
    extract_text_messages,
    is_valid_secret,
    is_allowed,
    parse_allowlist,
)


def test_build_session_id_includes_chat_and_user() -> None:
    session_id = build_session_id(chat_id=123, user_id=456)
    assert session_id == "telegram:chat-123:user-456"


def test_build_reset_session_id_includes_token() -> None:
    session_id = build_reset_session_id(chat_id=1, user_id=2, reset_token="abc")
    assert session_id == "telegram:chat-1:user-2:reset-abc"


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


def test_classify_text_message_recognizes_commands() -> None:
    assert classify_text_message("/start") == ("command", "/start")
    assert classify_text_message("/help") == ("command", "/help")
    assert classify_text_message("/reset") == ("command", "/reset")
    assert classify_text_message("hello") == ("text", "hello")


def test_is_valid_secret_checks_header() -> None:
    headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
    assert is_valid_secret(headers, "secret") is True
    assert is_valid_secret(headers, "wrong") is False


def test_parse_allowlist_handles_empty() -> None:
    assert parse_allowlist(None) == set()
    assert parse_allowlist("") == set()


def test_parse_allowlist_parses_ids() -> None:
    assert parse_allowlist("1, 2,3") == {1, 2, 3}


def test_is_allowed_with_allowlist() -> None:
    allowed_chats = {10}
    allowed_users = {42}
    assert is_allowed(10, 99, allowed_chats, allowed_users) is True
    assert is_allowed(99, 42, allowed_chats, allowed_users) is True
    assert is_allowed(99, 100, allowed_chats, allowed_users) is False
