"""Policy query helpers."""

from typing import List

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.policy import Policy
from src.cyberagent.db.models.policy import (
    get_policy as _get_policy,
    get_system_policy_prompts as _get_system_policy_prompts,
    get_team_policy_prompts as _get_team_policy_prompts,
)
from src.cyberagent.db.models.system import get_system_from_agent_id

DEFAULT_BASELINE_POLICIES: tuple[tuple[str, str], ...] = (
    (
        "task_completion_criteria",
        "Approve only when task output directly addresses task objective and is actionable.",
    ),
    (
        "evidence_requirements",
        "Task results must include concrete evidence, sources, or explicit assumptions.",
    ),
    (
        "safety_and_scope",
        "Reject outputs that exceed scope, contain unsafe instructions, or invent facts.",
    ),
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


def ensure_baseline_policies_for_assignee(agent_id: str) -> int:
    """
    Ensure a minimum team policy set exists for the assignee's team.

    Returns:
        Number of policies created.
    """
    system = get_system_from_agent_id(agent_id)
    if system is None:
        raise ValueError(f"System '{agent_id}' is not registered.")
    db = next(get_db())
    try:
        existing_count = (
            db.query(Policy)
            .filter(
                Policy.team_id == system.team_id,
                Policy.system_id.is_(None),
            )
            .count()
        )
        if existing_count > 0:
            return 0

        for name, content in DEFAULT_BASELINE_POLICIES:
            db.add(
                Policy(
                    team_id=system.team_id,
                    system_id=None,
                    name=name,
                    content=content,
                )
            )
        db.commit()
        return len(DEFAULT_BASELINE_POLICIES)
    finally:
        db.close()
