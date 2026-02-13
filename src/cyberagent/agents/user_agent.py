"""Canonical user-agent exports.

This module currently re-exports the legacy implementation while migration is
in progress.
"""

from src.agents.user_agent import ChannelContext, UserAgent

__all__ = ["ChannelContext", "UserAgent"]
