"""Team lookup helpers."""

from src.cyberagent.db.models.team import get_team as _get_team


def get_team(team_id: int):
    """Return a team by id."""
    return _get_team(team_id)
