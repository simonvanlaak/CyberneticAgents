"""Strategy orchestration helpers."""

from __future__ import annotations

from src.cyberagent.db.models.strategy import (
    Strategy,
    get_strategy as _get_strategy,
    get_teams_active_strategy as _get_teams_active_strategy,
)
from src.cyberagent.db.session_context import managed_session


def get_strategy(strategy_id: int):
    """Return a strategy by id."""
    return _get_strategy(strategy_id)


def get_teams_active_strategy(team_id: int):
    """Return the active strategy for a team."""
    return _get_teams_active_strategy(team_id)


def create_strategy(
    team_id: int,
    purpose_id: int,
    name: str,
    description: str,
    result: str = "",
) -> Strategy:
    """Create and persist a strategy."""
    strategy = Strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name=name,
        description=description,
        result=result,
    )
    with managed_session() as session:
        session.add(strategy)
        session.flush()
        session.commit()
        session.refresh(strategy)
        session.expunge(strategy)
    return strategy


def update_strategy_fields(
    strategy: Strategy, name: str | None = None, description: str | None = None
) -> None:
    """Update a strategy's name/description if provided."""
    if name:
        strategy.name = name
    if description:
        strategy.description = description

    if isinstance(strategy, Strategy):
        with managed_session(commit=True) as session:
            session.merge(strategy)
        return

    update_callable = getattr(strategy, "update", None)
    if callable(update_callable):
        update_callable()
