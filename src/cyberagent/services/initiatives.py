"""Initiative orchestration helpers."""

from src.cyberagent.db.models.initiative import (
    Initiative,
    get_initiative as _get_initiative,
)
from src.enums import Status


def start_initiative(initiative_id: int) -> Initiative:
    """
    Mark an initiative as in-progress.

    Args:
        initiative_id: Initiative identifier.

    Returns:
        The initiative record.

    Raises:
        ValueError: If the initiative does not exist.
    """
    initiative = _get_initiative(initiative_id)
    if initiative is None:
        raise ValueError(f"Initiative with id {initiative_id} not found")
    initiative.set_status(Status.IN_PROGRESS)
    initiative.update()
    return initiative


def get_initiative_by_id(initiative_id: int) -> Initiative:
    """
    Fetch an initiative or raise if missing.
    """
    initiative = _get_initiative(initiative_id)
    if initiative is None:
        raise ValueError(f"Initiative with id {initiative_id} not found")
    return initiative


def create_initiative(
    team_id: int,
    strategy_id: int,
    name: str,
    description: str,
) -> Initiative:
    """
    Create and persist an initiative.
    """
    initiative = Initiative(
        team_id=team_id,
        strategy_id=strategy_id,
        name=name,
        description=description,
    )
    initiative.add()
    return initiative


def update_initiative_fields(
    initiative: Initiative,
    name: str | None = None,
    description: str | None = None,
) -> None:
    """
    Update initiative fields if provided.
    """
    if name:
        initiative.name = name
    if description:
        initiative.description = description
    initiative.update()
