from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageRoute:
    channel: str
    session_id: str


def build_session_key(route: MessageRoute) -> str:
    """
    Build the canonical session key from channel and session id.

    Args:
        route: Routing metadata for a message.

    Returns:
        Canonical session key string.
    """
    return f"{route.channel}:{route.session_id}"


def is_reply_route_allowed(origin: MessageRoute, reply: MessageRoute) -> bool:
    """
    Determine whether a reply can be sent to the given route.

    Replies must remain on the same channel and session as the origin.

    Args:
        origin: The route of the original inbound message.
        reply: The candidate reply route.

    Returns:
        True when the reply route matches the origin channel and session.
    """
    return origin.channel == reply.channel and origin.session_id == reply.session_id
