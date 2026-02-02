from __future__ import annotations

from src.cyberagent.channels.telegram import parser


def test_parse_blocklist_returns_ints() -> None:
    assert parser.parse_blocklist(None) == set()
    assert parser.parse_blocklist("") == set()
    assert parser.parse_blocklist("123, 456,abc, 789") == {123, 456, 789}


def test_is_allowed_respects_blocklist_over_allowlist() -> None:
    allowed_chats = {1}
    allowed_users = {10}
    blocked_chats = {1}
    blocked_users = {99}

    assert (
        parser.is_allowed(
            chat_id=1,
            user_id=10,
            allowed_chats=allowed_chats,
            allowed_users=allowed_users,
            blocked_chats=blocked_chats,
            blocked_users=blocked_users,
        )
        is False
    )

    assert (
        parser.is_allowed(
            chat_id=2,
            user_id=99,
            allowed_chats=allowed_chats,
            allowed_users=allowed_users,
            blocked_chats=blocked_chats,
            blocked_users=blocked_users,
        )
        is False
    )


def test_is_allowed_defaults_to_true_when_no_allowlists() -> None:
    assert (
        parser.is_allowed(
            chat_id=1,
            user_id=2,
            allowed_chats=set(),
            allowed_users=set(),
            blocked_chats=set(),
            blocked_users=set(),
        )
        is True
    )
