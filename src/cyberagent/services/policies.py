"""Policy query helpers."""

from typing import List

from src.cyberagent.db.models.policy import (
    get_policy as _get_policy,
    get_system_policy_prompts as _get_system_policy_prompts,
    get_team_policy_prompts as _get_team_policy_prompts,
)


def get_system_policy_prompts(agent_id: str) -> List[str]:
    """
    Return policy prompts for a given agent.

    Args:
        agent_id: Agent identifier string.
    """
    return _get_system_policy_prompts(agent_id)


def get_policy_by_id(policy_id: int):
    """Return a policy by id."""
    return _get_policy(policy_id)


def get_team_policy_prompts(agent_id: str) -> List[str]:
    """Return team policy prompts for a given agent."""
    return _get_team_policy_prompts(agent_id)
