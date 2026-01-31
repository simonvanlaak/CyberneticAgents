# -*- coding: utf-8 -*-
"""
Utility functions for agent management.
"""

from autogen_core import AgentId


def get_user_agent_id() -> AgentId:
    """Get the user agent ID."""
    return AgentId.from_str("UserAgent/root")
