from __future__ import annotations

from src.cyberagent.channels.routing import (
    MessageRoute,
    build_session_key,
    is_reply_route_allowed,
)


def test_build_session_key_uses_channel_and_session() -> None:
    route = MessageRoute(channel="telegram", session_id="telegram:chat-1:user-2")

    assert build_session_key(route) == "telegram:telegram:chat-1:user-2"


def test_reply_route_allows_same_channel_and_session() -> None:
    origin = MessageRoute(channel="cli", session_id="cli-main")
    reply = MessageRoute(channel="cli", session_id="cli-main")

    assert is_reply_route_allowed(origin, reply) is True


def test_reply_route_rejects_cross_channel() -> None:
    origin = MessageRoute(channel="telegram", session_id="telegram:chat-1:user-2")
    reply = MessageRoute(channel="cli", session_id="cli-main")

    assert is_reply_route_allowed(origin, reply) is False


def test_reply_route_rejects_cross_session() -> None:
    origin = MessageRoute(channel="telegram", session_id="telegram:chat-1:user-2")
    reply = MessageRoute(channel="telegram", session_id="telegram:chat-9:user-9")

    assert is_reply_route_allowed(origin, reply) is False
