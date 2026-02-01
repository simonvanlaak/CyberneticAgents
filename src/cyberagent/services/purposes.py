"""Purpose helpers."""

from src.cyberagent.db.models.purpose import (
    get_or_create_default_purpose as _get_or_create_default_purpose,
)


def get_or_create_default_purpose(team_id: int):
    """Return the default purpose for a team, creating it if needed."""
    return _get_or_create_default_purpose(team_id)
